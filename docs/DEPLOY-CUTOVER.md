# Cut-over runbook: v1.4 (minister_management) → wos-events v2 on Cloud Run + GCS FUSE

Status: **prepared, never executed.** Nothing here has been run against Google Cloud. Every command
is for a human operator during an agreed maintenance window. Read it end to end before starting.

Why a runbook (review H1/H2): the v2 app no longer imports a v1.4 database at startup. A normal boot
on a v1.4 file **refuses to start** (`LegacyDatabaseError`). The import is a one-off command
(`python -m core.migrate`). After it, guard views make any v1.4 instance fail loudly (it cannot boot,
and its writes raise "cannot modify players because it is a view") instead of writing to ghost tables.
A v1.4 rollback therefore means **restoring the pre-v2 file**, not just redeploying v1.4.

SQLite on GCS FUSE has no cross-host locking. There must be exactly ONE writer at any time: the
service runs with `--max-instances 1`, and during the import nothing else may write.

## 0. Variables

```bash
export PROJECT_ID=<project>                 # gcloud config get-value project
export REGION=us-central1
export SERVICE=ministry-management          # Cloud Run service (with a "y")
export BUCKET=<bucket holding minister.db>  # see: gcloud run services describe $SERVICE --region $REGION
export DB_OBJECT=minister.db
export IMAGE=gcr.io/$PROJECT_ID/wos-events:v2-$(git rev-parse --short HEAD)
export JOB=wos-events-migrate-v14
export TS=$(date -u +%Y%m%dT%H%M%SZ)
gcloud config set project $PROJECT_ID
```

Record the current (v1.4) revision so rollback can route back to it:

```bash
export V14_REVISION=$(gcloud run services describe $SERVICE --region $REGION \
    --format='value(status.traffic[0].revisionName)')
export V14_IMAGE=$(gcloud run revisions describe $V14_REVISION --region $REGION \
    --format='value(spec.containers[0].image)')
echo "v1.4 revision: $V14_REVISION image: $V14_IMAGE"
```

## 1. Rehearse on a copy (days before, no window needed)

```bash
gcloud storage cp gs://$BUCKET/$DB_OBJECT ./rehearsal.db
cd backend
python -m core.migrate --db ../rehearsal.db --check     # read-only: v1.4_import_pending=True + row counts
python -m core.migrate --db ../rehearsal.db             # must print "OK (v1.4 import verified: counts match)"
python -m core.migrate --db ../rehearsal.db --check     # schema_version=2, profiles == v1.4 players
```

The import log lists what it normalised: `fids_trimmed` (legacy FIDs with stray whitespace),
`fids_kept_untrimmed` (would collide), `nonstandard_fids` (non-digit FIDs, kept and reachable) and
`fractional_crystal_fids` (crystal values like 12.5, kept exactly). Optionally boot the v2 app on the
rehearsal copy locally and click through admin + player flows. Delete `rehearsal.db*` afterwards (real
player data).

## 2. Maintenance window: stop all writes

Announce the window. Then make the v1.4 service unreachable from the internet so it receives no
requests (and therefore writes nothing), without deleting anything:

```bash
gcloud run services update $SERVICE --region $REGION --ingress internal
curl -s -o /dev/null -w '%{http_code}\n' https://<public domain>/health   # expect 403/404, not 200
```

Wait ~1 minute so in-flight requests finish.

## 3. Back up the database object (two independent copies)

```bash
# a) object versioning: every overwrite keeps the previous generation
gcloud storage buckets update gs://$BUCKET --versioning
export V14_GENERATION=$(gcloud storage objects describe gs://$BUCKET/$DB_OBJECT --format='value(generation)')
echo "v1.4 generation: $V14_GENERATION"

# b) explicit copies: one in the bucket, one off-bucket
gcloud storage cp gs://$BUCKET/$DB_OBJECT gs://$BUCKET/backups/$DB_OBJECT.v14-$TS
gcloud storage cp gs://$BUCKET/$DB_OBJECT ./backups/$DB_OBJECT.v14-$TS
sqlite3 ./backups/$DB_OBJECT.v14-$TS 'PRAGMA integrity_check; SELECT COUNT(*) FROM players; SELECT COUNT(*) FROM assignments;'
```

Write the two counts down: step 6 compares against them.

## 4. Build the v2 image

```bash
gcloud builds submit --tag $IMAGE .
```

## 5. Run the import as a one-off Cloud Run job (single writer)

The job uses the same image and mounts the same bucket. It runs `python -m core.migrate`, which takes
the SQLite write lock, re-checks the schema version inside the transaction, writes
`minister.db.pre-v2-<UTC>.bak` (as `.bak.partial`, renamed only after COMMIT), imports in one
transaction and verifies the row counts. Exit status non-zero = nothing changed (rolled back).

```bash
gcloud run jobs create $JOB \
    --image $IMAGE \
    --region $REGION \
    --command python \
    --args=-m,core.migrate,--db,/data/$DB_OBJECT \
    --set-env-vars FLASK_ENV=production,DATABASE_PATH=/data/$DB_OBJECT \
    --add-volume name=data,type=cloud-storage,bucket=$BUCKET \
    --add-volume-mount volume=data,mount-path=/data \
    --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 900 \
    --memory 1Gi --cpu 1

gcloud run jobs execute $JOB --region $REGION --wait
```

(Alternative without a job: deploy step 7 once with `--update-env-vars MIGRATE_V14=1`, then
redeploy without it. The job is preferred: the import is explicit, logged separately, and the
service never runs with the import flag on.)

## 6. Verify

```bash
gcloud logging read "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB\"" \
    --limit 200 --format='value(textPayload)' --freshness 1h | tac
```

Required in the log: `before: ... v1.4_import_pending=True`, `after: ... schema_version=2`, and
`OK (v1.4 import verified: counts match)`. Then check the file independently:

```bash
gcloud storage ls -l "gs://$BUCKET/$DB_OBJECT*"            # minister.db + exactly ONE .pre-v2-*.bak, no .partial
gcloud storage cp gs://$BUCKET/$DB_OBJECT ./backups/$DB_OBJECT.v2-$TS
sqlite3 ./backups/$DB_OBJECT.v2-$TS "PRAGMA integrity_check;
  SELECT 'profiles', COUNT(*) FROM profiles;          -- = v1.4 players (step 3)
  SELECT 'applications', COUNT(*) FROM applications;  -- = v1.4 players
  SELECT 'assignments', COUNT(*) FROM ministry_assignments;  -- = v1.4 assignments - orphans (logged)
  SELECT 'rounds', COUNT(*), MAX(name) FROM rounds;   -- 1, 'Imported from previous system'
  SELECT 'version', MAX(version) FROM schema_version; -- 2
  SELECT type, name FROM sqlite_master WHERE name IN ('players','assignments','time_preferences');  -- views"
```

If anything is off: **stop and roll back (R1)**. Do not deploy.

## 7. Deploy v2 (one instance, never more)

```bash
gcloud run deploy $SERVICE \
    --image $IMAGE \
    --region $REGION \
    --execution-environment gen2 \
    --min-instances 1 \
    --max-instances 1 \
    --memory 512Mi --cpu 1 --timeout 300 \
    --set-env-vars FLASK_ENV=production,DATABASE_PATH=/data/$DB_OBJECT,TRUSTED_PROXY_HOPS=1 \
    --remove-env-vars MIGRATE_V14,ALLOW_INSECURE_DEV \
    --set-secrets SECRET_KEY=minister-secret-key:latest,ADMIN_PASSWORD=admin-password:latest,MINISTER_PASSWORD=minister-password:latest \
    --add-volume name=data,type=cloud-storage,bucket=$BUCKET \
    --add-volume-mount volume=data,mount-path=/data

export V2_REVISION=$(gcloud run services describe $SERVICE --region $REGION \
    --format='value(status.latestReadyRevisionName)')
gcloud run services logs read $SERVICE --region $REGION --limit 50   # no ConfigError / LegacyDatabaseError
```

The secrets must hold real values: v2 refuses to start with a missing/placeholder `SECRET_KEY` or a
default password (`admin123`, ...). `--max-instances 1` is mandatory (GCS FUSE + SQLite).

## 8. Re-open and smoke test

```bash
gcloud run services update $SERVICE --region $REGION --ingress all
B=https://<public domain>
curl -s $B/health                                   # {"status":"healthy"}
curl -s $B/api/settings/public                      # {"state_number":"2807"}
curl -s $B/api/events/ministry/current              # the imported round, with the old settings
curl -s $B/api/profile/<a known FID>                # 200
```

In the browser: admin login, player list count = v1.4 count, one assignment day, Excel export, one
player lookup and edit. End the window.

## 9. Afterwards

- Keep the `.pre-v2-*.bak` object, the `backups/` copies and bucket versioning for at least one full
  event cycle. Then optionally `gcloud storage buckets update gs://$BUCKET --no-versioning`.
- `gcloud run jobs delete $JOB --region $REGION` once the window is closed.
- Delete local copies of player data (`./backups/*`, `rehearsal.db`) when no longer needed.

---

## Rollback

v1.4 **cannot** run on the migrated file (guard views stop it at boot). Rolling back = restore the
v1.4 file, then route traffic to the v1.4 revision.

### R1. The import failed or verification failed (v2 not deployed yet)

`python -m core.migrate` runs in one transaction: a failure leaves the file exactly as v1.4 left it and
removes its partial backup. Check, then reopen v1.4:

```bash
gcloud storage ls -l "gs://$BUCKET/$DB_OBJECT*"     # no .bak.partial; if a .pre-v2-*.bak exists the import COMMITTED -> use R2
gcloud run services update $SERVICE --region $REGION --ingress all
```

If verification (step 6) failed after a committed import, do R2 steps 2-4 (no v2 data to save).

### R2. v2 is live and must be rolled back

1. Stop traffic (v2 then writes nothing):
   ```bash
   gcloud run services update $SERVICE --region $REGION --ingress internal
   ```
2. Keep what v2 wrote since the cut-over (to reconcile by hand later):
   ```bash
   gcloud storage cp gs://$BUCKET/$DB_OBJECT ./backups/$DB_OBJECT.v2-at-rollback-$(date -u +%Y%m%dT%H%M%SZ)
   ```
3. Restore the v1.4 file (either source; they are the same bytes):
   ```bash
   # from the backup written by the import
   gcloud storage cp "gs://$BUCKET/$DB_OBJECT.pre-v2-<UTC>.bak" gs://$BUCKET/$DB_OBJECT
   # or from the object generation recorded in step 3
   gcloud storage cp "gs://$BUCKET/$DB_OBJECT#$V14_GENERATION" gs://$BUCKET/$DB_OBJECT
   ```
4. Put the v1.4 image back (one instance) and reopen. Redeploying the recorded v1.4 image is safer
   than routing to the old revision, which still carries the old `--max-instances 3`:
   ```bash
   gcloud run deploy $SERVICE --region $REGION --image $V14_IMAGE --min-instances 1 --max-instances 1
   gcloud run services update $SERVICE --region $REGION --ingress all
   curl -s https://<public domain>/api/settings/state-number      # a v1.4 endpoint answers again
   ```
   (Quick alternative if minutes matter:
   `gcloud run services update-traffic $SERVICE --region $REGION --to-revisions $V14_REVISION=100`.)

Submissions made on v2 between cut-over and rollback are only in the `v2-at-rollback` copy. They are
not merged automatically.

### Never do

- Never run v1.4 and v2 against the same file at the same time, and never `--max-instances` > 1.
- Never "fix" a v2 database by deleting it from the bucket: restore a backup/generation instead.
- Never delete the guard views to let v1.4 start on a migrated file: its writes would land in tables
  v2 never reads (the "ghost table" problem the guards exist for).
