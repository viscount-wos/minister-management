import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { isRtl } from './i18n/index';
import Home from './pages/Home';
import PlayerForm from './pages/PlayerForm';
import UpdateSubmission from './pages/UpdateSubmission';
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import PublishedSchedule from './pages/PublishedSchedule';
import PlayerGuide from './pages/PlayerGuide';
import AdminGuide from './pages/AdminGuide';
import Changelog from './pages/Changelog';
import LanguageSelector from './components/LanguageSelector';
import ThemeSelector from './components/ThemeSelector';

function App() {
  const { i18n } = useTranslation();

  // Set document direction for RTL languages
  document.documentElement.dir = isRtl(i18n.language) ? 'rtl' : 'ltr';

  return (
    <Router>
      <div className="min-h-screen flex flex-col">
        {/* Both selectors share one wrapping row so they stack tidily on a
            phone instead of forcing the header wider than the screen. */}
        <header className="w-full py-3 px-4 flex flex-wrap items-center justify-end gap-x-5 gap-y-2">
          <ThemeSelector />
          <LanguageSelector />
        </header>
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/submit" element={<PlayerForm />} />
            <Route path="/update" element={<UpdateSubmission />} />
            <Route path="/schedule/:day" element={<PublishedSchedule />} />
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
            <Route path="/guide" element={<PlayerGuide />} />
            <Route path="/admin/guide" element={<AdminGuide />} />
            <Route path="/changelog" element={<Changelog />} />
          </Routes>
        </div>
        <footer className="mt-auto pb-4 text-center">
          <p className="text-xs italic text-theme-dim">compliments of the viscount, you're welcome 😂</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
