import { useState, useEffect, useRef } from 'react';
import type { FormEvent } from 'react';
import api from '../api/client';

interface Employee {
  id: number;
  full_name: string;
}

interface Category {
  id: number;
  title: string;
  title_display: string;
}

interface Incident {
  id: number;
  record: number;
  analysis: number | null;
  start_minutes: number;
  end_minutes: number;
  description?: string;
  severity?: string;
  created_at: string;
}

const sevColor = (s?: string) =>
  s === 'high' ? 'bg-red-100 text-red-700 border-red-200'
  : s === 'medium' ? 'bg-amber-100 text-amber-800 border-amber-200'
  : 'bg-gray-100 text-gray-600 border-gray-200';

// минуты (дробные) → "M:SS"
const fmtTime = (min: number) => {
  const total = Math.round(min * 60);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
};

interface Analysis {
  id: number;
  record: number;
  description: string;
  incidents: Incident[];
  created_at: string;
  updated_at: string;
}

interface Transcription {
  id: number;
  employee: number;
  employee_name: string;
  category: number | null;
  category_title: string | null;
  audio_url: string | null;
  text: string;
  record_datetime: string;
  analysis: Analysis | null;
  created_at: string;
}

// Локальная дата-время в формате для <input type="datetime-local">
function nowLocalDatetime(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export default function Transcriptions() {
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [filterEmployee, setFilterEmployee] = useState('');
  const [filterCategory, setFilterCategory] = useState('');

  // Modal
  const [showModal, setShowModal] = useState(false);
  const [newEmployeeId, setNewEmployeeId] = useState('');
  const [newCategoryId, setNewCategoryId] = useState('');
  const [newDatetime, setNewDatetime] = useState(nowLocalDatetime());
  const [newText, setNewText] = useState('');
  const [newFile, setNewFile] = useState<File | null>(null);
  const [creating, setCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Detail
  const [selected, setSelected] = useState<Transcription | null>(null);
  const [analysisDraft, setAnalysisDraft] = useState('');
  const [savingAnalysis, setSavingAnalysis] = useState(false);
  const [incStart, setIncStart] = useState('');
  const [incEnd, setIncEnd] = useState('');
  const [addingIncident, setAddingIncident] = useState(false);

  useEffect(() => {
    api.get('/api/staff/employees/').then((r) => setEmployees(r.data?.results ?? r.data ?? [])).catch(() => {});
    api.get('/api/staff/categories/').then((r) => setCategories(r.data?.results ?? r.data ?? [])).catch(() => {});
  }, []);

  const fetchTranscriptions = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterEmployee) params.employee = filterEmployee;
      if (filterCategory) params.category = filterCategory;
      const { data } = await api.get('/api/staff/transcriptions/', { params });
      setTranscriptions(Array.isArray(data) ? data : data.results ?? []);
    } catch {
      setError('Не удалось загрузить транскрипции');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTranscriptions(); }, [filterEmployee, filterCategory]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!newFile || !newEmployeeId) return;
    setCreating(true);
    try {
      const formData = new FormData();
      formData.append('employee', newEmployeeId);
      if (newCategoryId) formData.append('category', newCategoryId);
      formData.append('record_datetime', new Date(newDatetime).toISOString());
      formData.append('audio', newFile);
      formData.append('text', newText);
      const { data } = await api.post('/api/staff/transcriptions/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTranscriptions((prev) => [data, ...prev]);
      setShowModal(false);
      setNewEmployeeId(''); setNewCategoryId(''); setNewDatetime(nowLocalDatetime()); setNewText(''); setNewFile(null);
    } catch {
      setError('Не удалось создать запись');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить запись?')) return;
    try {
      await api.delete(`/api/staff/transcriptions/${id}/`);
      setTranscriptions((prev) => prev.filter((t) => t.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch { setError('Ошибка удаления'); }
  };

  const openDetail = (t: Transcription) => {
    setSelected(t);
    setAnalysisDraft(t.analysis?.description ?? '');
    setIncStart(''); setIncEnd('');
  };

  // Перечитывает запись с сервера и синхронизирует список + карточку
  const refreshSelected = async (id: number) => {
    const { data } = await api.get(`/api/staff/transcriptions/${id}/`);
    setSelected(data);
    setAnalysisDraft(data.analysis?.description ?? '');
    setTranscriptions((prev) => prev.map((t) => (t.id === id ? data : t)));
  };

  const handleSaveAnalysis = async () => {
    if (!selected) return;
    setSavingAnalysis(true);
    setError('');
    try {
      if (selected.analysis) {
        await api.patch(`/api/staff/analyses/${selected.analysis.id}/`, { description: analysisDraft });
      } else {
        await api.post('/api/staff/analyses/', { record: selected.id, description: analysisDraft });
      }
      await refreshSelected(selected.id);
    } catch {
      setError('Не удалось сохранить анализ');
    } finally {
      setSavingAnalysis(false);
    }
  };

  const handleAddIncident = async (e: FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setAddingIncident(true);
    setError('');
    try {
      await api.post('/api/staff/incidents/', {
        record: selected.id,
        analysis: selected.analysis?.id ?? null,
        start_minutes: parseFloat(incStart),
        end_minutes: parseFloat(incEnd),
      });
      setIncStart(''); setIncEnd('');
      await refreshSelected(selected.id);
    } catch {
      setError('Не удалось добавить инцидент (проверьте, что конец не раньше начала)');
    } finally {
      setAddingIncident(false);
    }
  };

  const handleDeleteIncident = async (incId: number) => {
    if (!selected) return;
    try {
      await api.delete(`/api/staff/incidents/${incId}/`);
      await refreshSelected(selected.id);
    } catch { setError('Не удалось удалить инцидент'); }
  };

  const categoryBadgeColor = (title: string | null) => {
    if (title === 'Рабочие моменты') return 'bg-blue-100 text-blue-700';
    if (title === 'Переговоры') return 'bg-purple-100 text-purple-700';
    return 'bg-gray-100 text-gray-600';
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Записи транскрибации</h2>
        <button
          onClick={() => setShowModal(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          + Новая запись
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={filterEmployee}
          onChange={(e) => setFilterEmployee(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          <option value="">Все сотрудники</option>
          {employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
        </select>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          <option value="">Все категории</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.title_display}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="text-center text-gray-500 py-12">Загрузка...</div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Сотрудник</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Категория</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Текст (превью)</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Дата</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {transcriptions.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-400">Записи не найдены</td></tr>
              ) : transcriptions.map((t) => (
                <tr
                  key={t.id}
                  onClick={() => openDetail(t)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-gray-700 font-mono">#{t.id}</td>
                  <td className="px-4 py-3 text-gray-800 font-medium">{t.employee_name}</td>
                  <td className="px-4 py-3">
                    {t.category_title ? (
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${categoryBadgeColor(t.category_title)}`}>
                        {t.category_title}
                      </span>
                    ) : <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{t.text || <span className="italic text-gray-400">Нет текста</span>}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(t.record_datetime).toLocaleString('ru-RU')}</td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => handleDelete(t.id)}
                      className="text-xs text-red-500 hover:text-red-700">Удалить</button>
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
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Новая запись транскрибации</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Сотрудник</label>
                <select required value={newEmployeeId} onChange={(e) => setNewEmployeeId(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                  <option value="">Выберите сотрудника</option>
                  {employees.map((emp) => <option key={emp.id} value={emp.id}>{emp.full_name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Категория</label>
                <select value={newCategoryId} onChange={(e) => setNewCategoryId(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                  <option value="">— Без категории —</option>
                  {categories.map((c) => <option key={c.id} value={c.id}>{c.title_display}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Дата и время записи</label>
                <input type="datetime-local" required value={newDatetime} onChange={(e) => setNewDatetime(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Аудиофайл</label>
                <div
                  className="border-2 border-dashed border-gray-300 rounded-md px-4 py-6 text-center cursor-pointer hover:border-indigo-400 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  {newFile ? (
                    <p className="text-sm text-indigo-600 font-medium">{newFile.name}</p>
                  ) : (
                    <p className="text-sm text-gray-400">Нажмите для выбора файла (mp3, wav, ogg)</p>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={(e) => setNewFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Текст транскрипции</label>
                <textarea
                  value={newText}
                  onChange={(e) => setNewText(e.target.value)}
                  rows={4}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                  placeholder="Текст можно ввести вручную или оставить пустым..."
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">Отмена</button>
                <button type="submit" disabled={creating || !newFile || !newEmployeeId}
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium disabled:opacity-60">
                  {creating ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-800">Запись #{selected.id}</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  {selected.employee_name}
                  {selected.category_title && (
                    <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-medium ${categoryBadgeColor(selected.category_title)}`}>
                      {selected.category_title}
                    </span>
                  )}
                </p>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>

            {selected.audio_url && (
              <div className="mb-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Аудио</p>
                <audio controls src={selected.audio_url} className="w-full" />
              </div>
            )}

            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Транскрипция</p>
              {selected.text ? (
                <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 rounded-md p-4 leading-relaxed">
                  {selected.text}
                </pre>
              ) : (
                <p className="text-gray-400 italic text-sm">Текст транскрипции отсутствует</p>
              )}
            </div>

            {/* Анализ */}
            <div className="mt-6 border-t border-gray-100 pt-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Анализ</p>
              <textarea
                value={analysisDraft}
                onChange={(e) => setAnalysisDraft(e.target.value)}
                rows={3}
                placeholder="Описание анализа записи..."
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              />
              <div className="mt-2">
                <button onClick={handleSaveAnalysis} disabled={savingAnalysis}
                  className="px-3 py-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium disabled:opacity-60">
                  {savingAnalysis ? 'Сохранение...' : selected.analysis ? 'Обновить анализ' : 'Создать анализ'}
                </button>
              </div>
            </div>

            {/* Инциденты */}
            <div className="mt-6 border-t border-gray-100 pt-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Инциденты</p>
              {selected.analysis && selected.analysis.incidents.length > 0 ? (
                <ul className="space-y-2 mb-3">
                  {selected.analysis.incidents.map((inc) => (
                    <li key={inc.id} className={`border rounded-md px-3 py-2 text-sm ${sevColor(inc.severity)}`}>
                      <div className="flex items-center justify-between mb-0.5">
                        <div className="flex items-center gap-2">
                          {inc.severity && <span className="text-[11px] font-bold uppercase">{inc.severity}</span>}
                          {(inc.start_minutes !== 0 || inc.end_minutes !== 0) && (
                            <span className="text-xs opacity-70">⏱ {fmtTime(inc.start_minutes)}–{fmtTime(inc.end_minutes)}</span>
                          )}
                        </div>
                        <button onClick={() => handleDeleteIncident(inc.id)}
                          className="text-xs text-red-500 hover:text-red-700">Удалить</button>
                      </div>
                      {inc.description || '—'}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-400 italic mb-3">Инцидентов нет</p>
              )}
              <form onSubmit={handleAddIncident} className="flex items-end gap-2">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Начало (мин)</label>
                  <input type="number" step="0.1" min="0" required value={incStart} onChange={(e) => setIncStart(e.target.value)}
                    className="w-24 border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Конец (мин)</label>
                  <input type="number" step="0.1" min="0" required value={incEnd} onChange={(e) => setIncEnd(e.target.value)}
                    className="w-24 border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
                </div>
                <button type="submit" disabled={addingIncident}
                  className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-900 text-white rounded-md font-medium disabled:opacity-60">
                  {addingIncident ? '...' : '+ Добавить'}
                </button>
              </form>
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
