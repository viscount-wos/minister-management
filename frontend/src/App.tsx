import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './shell/Layout';
import Home from './shell/Home';
import Changelog from './shell/Changelog';
import LegacyRedirect from './shell/LegacyRedirect';
import { TimezoneProvider } from './shared/TimezoneContext';
import MinistryHome from './events/ministry/MinistryHome';
import ApplicationWizard from './events/ministry/ApplicationWizard';
import PublishedSchedule from './events/ministry/PublishedSchedule';
import PlayerGuide from './events/ministry/PlayerGuide';
import AdminLogin from './events/ministry/admin/AdminLogin';
import AdminDashboard from './events/ministry/admin/AdminDashboard';
import AdminGuide from './events/ministry/admin/AdminGuide';
import TyrantPage from './events/tyrant/TyrantPage';
import SvsPage from './events/svs/SvsPage';
import TalPage from './events/tal/TalPage';

function App() {
  return (
    <TimezoneProvider>
      <Router>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/changelog" element={<Changelog />} />

            {/* Ministry */}
            <Route path="/ministry" element={<MinistryHome />} />
            <Route path="/ministry/apply" element={<ApplicationWizard />} />
            {/* v1.4's new (/submit) and update (/update) pages are one wizard now: the FID decides new vs edit */}
            <Route path="/ministry/submit" element={<LegacyRedirect to="/ministry/apply" />} />
            <Route path="/ministry/update" element={<LegacyRedirect to="/ministry/apply" />} />
            <Route path="/ministry/schedule/:day" element={<PublishedSchedule />} />
            <Route path="/ministry/guide" element={<PlayerGuide />} />

            {/* Other events */}
            <Route path="/tyrant" element={<TyrantPage />} />
            <Route path="/svs" element={<SvsPage />} />
            <Route path="/tal" element={<TalPage />} />

            {/* Admin (unchanged URLs) */}
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
            <Route path="/admin/guide" element={<AdminGuide />} />

            {/* v1.x URLs, kept working for bookmarks and shared links */}
            <Route path="/submit" element={<LegacyRedirect to="/ministry/apply" />} />
            <Route path="/apply" element={<LegacyRedirect to="/ministry/apply" />} />
            <Route path="/update" element={<LegacyRedirect to="/ministry/apply" />} />
            <Route path="/schedule/:day" element={<LegacyRedirect to="/ministry/schedule/:day" />} />
            <Route path="/guide" element={<LegacyRedirect to="/ministry/guide" />} />
            <Route path="/ministry/admin" element={<LegacyRedirect to="/admin" />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Router>
    </TimezoneProvider>
  );
}

export default App;
