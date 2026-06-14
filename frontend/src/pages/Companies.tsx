import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import api from '../api/client';

interface Company {
  id: number;
  name: string;
  api_key: string;
  encryption_key: string;
  created_at: string;
}

function KeyField({ label, value }: { label: string; value: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <dt className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</dt>
      <dd className="flex items-center gap-2">
        <code className="text-xs font-mono bg-gray-100 rounded px-2 py-1 text-gray-700 break-all flex-1">
          {visible ? value : '••••••••••••••••••••••••••••••••'}
        </code>
        <button
          onClick={() => setVisible((v) => !v)}
          className="text-xs text-indigo-600 hover:text-indigo-800 whitespace-nowrap"
        >
          {visible ? 'Скрыть' : 'Показать'}
        </button>
        <button
          onClick={() => navigator.clipboard.writeText(value)}
          className="text-xs text-gray-400 hover:text-gray-600 whitespace-nowrap"
        >
          Копировать
        </button>
      </dd>
    </div>
  );
}

export default function Companies() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [showDetail, setShowDetail] = useState<Company | null>(null);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const fetchCompanies = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/staff/companies/');
      setCompanies(Array.isArray(data) ? data : data.results ?? []);
    } catch {
      setError('Не удалось загрузить компании');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const { data } = await api.post('/api/staff/companies/', { name: newName });
      setCompanies((prev) => [data, ...prev]);
      setShowModal(false);
      setNewName('');
      setShowDetail(data);
    } catch {
      setError('Не удалось создать компанию');
    } finally {
      setCreating(false);
    }
  };

  const handleRegenerate = async (id: number) => {
    setRegenerating(true);
    try {
      const { data } = await api.post(`/api/staff/companies/${id}/regenerate-keys/`);
      setCompanies((prev) => prev.map((c) => (c.id === id ? data : c)));
      setShowDetail(data);
    } catch {
      setError('Не удалось перегенерировать ключи');
    } finally {
      setRegenerating(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить компанию?')) return;
    try {
      await api.delete(`/api/staff/companies/${id}/`);
      setCompanies((prev) => prev.filter((c) => c.id !== id));
      setShowDetail(null);
    } catch {
      setError('Не удалось удалить компанию');
    }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Компании</h2>
        <button
          onClick={() => setShowModal(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          + Новая компания
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Загрузка...</div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Название</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Дата создания</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {companies.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center text-gray-400">Компании не найдены</td>
                </tr>
              ) : companies.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-700 font-mono">#{c.id}</td>
                  <td className="px-4 py-3 text-gray-800 font-medium">{c.name}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(c.created_at).toLocaleDateString('ru-RU')}</td>
                  <td className="px-4 py-3 flex gap-2">
                    <button
                      onClick={() => setShowDetail(c)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                      Ключи
                    </button>
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="text-xs text-red-500 hover:text-red-700 font-medium"
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Новая компания</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Название</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="ООО Пример"
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
                  Отмена
                </button>
                <button type="submit" disabled={creating}
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium transition-colors disabled:opacity-60">
                  {creating ? 'Создание...' : 'Создать'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Detail / Keys Modal */}
      {showDetail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold text-gray-800">{showDetail.name}</h3>
              <button onClick={() => setShowDetail(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
            <dl className="space-y-4">
              <KeyField label="Ключ компании (API Key)" value={showDetail.api_key} />
              <KeyField label="Ключ шифрования" value={showDetail.encryption_key} />
            </dl>
            <div className="mt-6 flex justify-between">
              <button
                onClick={() => handleRegenerate(showDetail.id)}
                disabled={regenerating}
                className="text-sm text-amber-600 hover:text-amber-800 font-medium disabled:opacity-60"
              >
                {regenerating ? 'Перегенерация...' : '🔄 Перегенерировать ключи'}
              </button>
              <button
                onClick={() => setShowDetail(null)}
                className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
