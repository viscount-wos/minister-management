import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './shell/Layout';
import Home from './shell/Home';
import LegacyRedirect from './shell/LegacyRedirect';
import { TimezoneProvider } from './shared/TimezoneContext';
import { PAGES } from './pages';

// Lazy pages (./pages.ts): the Suspense fallback lives in Layout, under the header.
const Changelog = PAGES.changelog.Component;
const MinistryHome = PAGES.ministryHome.Component;
const ApplicationWizard = PAGES.ministryApply.Component;
const PublishedSchedule = PAGES.ministrySchedule.Component;
const PlayerGuide = PAGES.ministryGuide.Component;
const AdminLogin = PAGES.adminLogin.Component;
const AdminShell = PAGES.adminShell.Component;
const AdminGuidePage = PAGES.adminGuide.Component;
const TyrantPage = PAGES.tyrantHome.Component;
const TyrantWizard = PAGES.tyrantApply.Component;
const SvsPage = PAGES.svs.Component;
const TalPage = PAGES.tal.Component;

function App() {
  return (
    <TimezoneProvider>
      <Router>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/changelog" element={<Changelog />} />

            {/* Minister (event key 'ministry'); canonical URLs under /minister */}
            <Route path="/minister" element={<MinistryHome />} />
            <Route path="/minister/apply" element={<ApplicationWizard />} />
            <Route path="/minister/schedule/:day" element={<PublishedSchedule />} />
            <Route path="/minister/guide" element={<PlayerGuide />} />
            {/* v1.4's new (/submit) and update (/update) pages are one wizard now: the FID decides new vs edit */}
            <Route path="/minister/submit" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/minister/update" element={<LegacyRedirect to="/minister/apply" />} />

            {/* Other events */}
            <Route path="/tyrant" element={<TyrantPage />} />
            <Route path="/tyrant/apply" element={<TyrantWizard />} />
            <Route path="/svs" element={<SvsPage />} />
            <Route path="/tal" element={<TalPage />} />

            {/* Event Management: one admin for every event; ?event=<key> picks the event (admin/paths.ts) */}
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/admin/dashboard" element={<AdminShell />} />
            <Route path="/admin/guide" element={<AdminGuidePage />} />

            {/* Older URLs, kept working for bookmarks and shared links (query string and hash kept) */}
            <Route path="/ministry" element={<LegacyRedirect to="/minister" />} />
            <Route path="/ministry/apply" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/ministry/submit" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/ministry/update" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/ministry/schedule/:day" element={<LegacyRedirect to="/minister/schedule/:day" />} />
            <Route path="/ministry/guide" element={<LegacyRedirect to="/minister/guide" />} />
            <Route path="/ministry/admin" element={<LegacyRedirect to="/admin?event=ministry" />} />
            <Route path="/minister/admin" element={<LegacyRedirect to="/admin?event=ministry" />} />
            <Route path="/submit" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/apply" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/update" element={<LegacyRedirect to="/minister/apply" />} />
            <Route path="/schedule/:day" element={<LegacyRedirect to="/minister/schedule/:day" />} />
            <Route path="/guide" element={<LegacyRedirect to="/minister/guide" />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Router>
    </TimezoneProvider>
  );
}

export default App;
