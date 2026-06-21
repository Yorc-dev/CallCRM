import { useState, useEffect, useCallback } from 'react';
import api from '../api/client';

interface Employee { id: number; full_name: string; }

interface Incident {
  id: number;
  start_minutes: number;
  end_minutes: number;
  description?: string;
  severity?: string;
}

const sevColor = (s?: string) =>
  s === 'high' ? 'bg-red-100 text-red-700 border-red-200'
  : s === 'medium' ? 'bg-amber-100 text-amber-800 border-amber-200'
  : 'bg-gray-100 text-gray-600 border-gray-200';

const fmtTime = (min: number) => {
  const total = Math.round(min * 60);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};

interface Analysis {
  id: number;
  record: number;
  description: string;
  incidents: Incident[];
  employee_name: string;
  company_name: string;
  record_datetime: string;
  created_at: string;
}

function unwrap(data: unknown): Analysis[] {
  if (Array.isArray(data)) return data as Analysis[];
  return ((data as { results?: Analysis[] })?.results) ?? [];
}

export default function Analyses() {
  const [items, setItems] = useState<Analysis[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Analysis | null>(null);

  const [employee, setEmployee] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  useEffect(() => {
    api.get('/api/staff/employees/')
      .then((r) => setEmployees(Array.isArray(r.data) ? r.data : r.data.results ?? []))
      .catch(() => {});
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { [k: string]: string } = {};
      if (employee) params.employee = employee;
      if (from) params.from = new Date(from).toISOString();
      if (to) params.to = new Date(to).toISOString();
      const { data } = await api.get('/api/staff/analyses/', { params });
      setItems(unwrap(data));
    } catch {
      setError('Не удалось загрузить анализы');
    } finally {
      setLoading(false);
    }
  }, [employee, from, to]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить анализ?')) return;
    try {
      await api.delete(`/api/staff/analyses/${id}/`);
      setItems((prev) => prev.filter((a) => a.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch { setError('Ошибка удаления'); }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Анализы</h2>
      </div>

      {/* Фильтры */}
      <div className="flex flex-wrap items-end gap-3 mb-4 bg-white border border-gray-200 rounded-lg p-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Сотрудник</label>
          <select value={employee} onChange={(e) => setEmployee(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
            <option value="">Все</option>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">С</label>
          <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">По</label>
          <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
        {(employee || from || to) && (
          <button onClick={() => { setEmployee(''); setFrom(''); setTo(''); }}
            className="px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">Сбросить</button>
        )}
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
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Сотрудник</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Компания</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Описание</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Инцидентов</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Дата записи</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-400">Анализов нет</td></tr>
              ) : items.map((a) => (
                <tr key={a.id} onClick={() => setSelected(a)} className="hover:bg-gray-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3 text-gray-700 font-mono">#{a.id}</td>
                  <td className="px-4 py-3 text-gray-800 font-medium">{a.employee_name}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs">{a.company_name}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-md truncate">{a.description || <span className="italic text-gray-400">—</span>}</td>
                  <td className="px-4 py-3 text-gray-600">{a.incidents.length}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(a.record_datetime).toLocaleString('ru-RU')}</td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => handleDelete(a.id)} className="text-xs text-red-500 hover:text-red-700">Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">Анализ #{selected.id}</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  {selected.employee_name} · {selected.company_name} · запись #{selected.record}
                </p>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>

            <div className="mb-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Описание</p>
              {selected.description ? (
                <p className="text-sm text-gray-700 bg-gray-50 rounded-md p-4 leading-relaxed">{selected.description}</p>
              ) : (
                <p className="text-gray-400 italic text-sm">Описание отсутствует</p>
              )}
            </div>

            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Инциденты</p>
              {selected.incidents.length === 0 ? (
                <p className="text-sm text-gray-400 italic">Инцидентов нет</p>
              ) : (
                <ul className="space-y-2">
                  {selected.incidents.map((inc) => (
                    <li key={inc.id} className={`border rounded-md px-3 py-2 text-sm ${sevColor(inc.severity)}`}>
                      <div className="flex items-center gap-2 mb-0.5">
                        {inc.severity && (
                          <span className="text-[11px] font-bold uppercase">{inc.severity}</span>
                        )}
                        {(inc.start_minutes !== 0 || inc.end_minutes !== 0) && (
                          <span className="text-xs opacity-70">⏱ {fmtTime(inc.start_minutes)}–{fmtTime(inc.end_minutes)}</span>
                        )}
                      </div>
                      {inc.description || '—'}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-6 text-right">
              <button onClick={() => setSelected(null)}
                className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors">
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
