#!/usr/bin/env node
// Repo-root entry point required by docs/SPEC.md. The real checker lives in
// frontend/scripts/check-i18n.mjs so it is inside the Docker build context
// (the frontend build stage copies only frontend/). Run either:
//   node scripts/check-i18n.mjs            (repo root)
//   cd frontend && npm run check:i18n
import '../frontend/scripts/check-i18n.mjs';
