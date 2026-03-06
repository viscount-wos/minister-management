import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText, Edit, Shield } from 'lucide-react';

export default function Home() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-accent mb-4">
            {t('home.title')}
          </h1>
          <p className="text-xl text-theme-dim">
            {t('home.subtitle')}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Submit New Application */}
          <button
            onClick={() => navigate('/submit')}
            className="bg-dark-card rounded-2xl p-8 border border-theme-border hover:bg-dark-card-hover transform hover:-translate-y-2 transition-all duration-300 group"
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-accent/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-accent/30 transition-colors">
                <FileText className="w-10 h-10 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text mb-3">
                {t('home.submitNew')}
              </h2>
              <p className="text-theme-dim">
                Submit your speedups and time preferences for ministry positions
              </p>
            </div>
          </button>

          {/* Update Submission */}
          <button
            onClick={() => navigate('/update')}
            className="bg-dark-card rounded-2xl p-8 border border-theme-border hover:bg-dark-card-hover transform hover:-translate-y-2 transition-all duration-300 group"
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-success/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-success/30 transition-colors">
                <Edit className="w-10 h-10 text-success" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text mb-3">
                {t('home.updateExisting')}
              </h2>
              <p className="text-theme-dim">
                Update your previously submitted information
              </p>
            </div>
          </button>

          {/* Admin Access */}
          <button
            onClick={() => navigate('/admin')}
            className="bg-dark-card rounded-2xl p-8 border border-theme-border hover:bg-dark-card-hover transform hover:-translate-y-2 transition-all duration-300 group"
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-accent/20 rounded-full flex items-center justify-center mb-6 group-hover:bg-accent/30 transition-colors">
                <Shield className="w-10 h-10 text-accent" />
              </div>
              <h2 className="text-2xl font-bold text-theme-text mb-3">
                {t('admin.title')}
              </h2>
              <p className="text-theme-dim">
                Manage players and assignments
              </p>
            </div>
          </button>
        </div>

        <div className="mt-12 text-center text-theme-dim text-sm">
          <p>All times are in UTC timezone</p>
        </div>
      </div>
    </div>
  );
}
