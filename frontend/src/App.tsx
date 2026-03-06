import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Home from './pages/Home';
import PlayerForm from './pages/PlayerForm';
import UpdateSubmission from './pages/UpdateSubmission';
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import LanguageSelector from './components/LanguageSelector';

function App() {
  const { i18n } = useTranslation();

  // Set document direction for RTL languages
  document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr';

  return (
    <Router>
      <div className="min-h-screen flex flex-col">
        <div className="fixed top-4 right-4 z-50">
          <LanguageSelector />
        </div>
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/submit" element={<PlayerForm />} />
            <Route path="/update" element={<UpdateSubmission />} />
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
          </Routes>
        </div>
        <footer className="app-footer mt-auto pb-4">
          <p>compliments of the viscount. you're welcome.</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
