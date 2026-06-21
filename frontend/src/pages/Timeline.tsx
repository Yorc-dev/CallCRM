import { useState, useEffect, useCallback } from 'react';
import api from '../api/client';

interface Employee { id: number; full_name: string; }
interface Category { id: number; title_display: string; }

interface Segment {
  id: number;
  employee: number;
  employee_name: string;
  category: number | null;
  category_title: string | null;
  audio_url: string | null;
  record_datetime: string;
  text: string;
}

function unwrap<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  return ((data as { results?: T[] })?.results) ?? [];
}

// Локальная дата для datetime-local (начало/конец дня по умолчанию)
function todayStart(): string {
  const d = new Date(); d.setHours(0, 0, 0, 0);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}
function nowLocal(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

const catColor = (t: string | null) =>
  t === 'Рабочие моменты' ? 'bg-blue-100 text-blue-700'
  : t === 'Переговоры' ? 'bg-purple-100 text-purple-700'
  : 'bg-gray-100 text-gray-500';

export default function Timeline() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [records, setRecords] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [employee, setEmployee] = useState('');
  const [from, setFrom] = useState(todayStart());
  const [to, setTo] = useState(nowLocal());
  const [category, setCategory] = useState('');

  useEffect(() => {
    api.get('/api/staff/employees/').then((r) => setEmployees(unwrap<Employee>(r.data))).catch(() => {});
    api.get('/api/staff/categories/').then((r) => setCategories(unwrap<Category>(r.data))).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: { [k: string]: string } = { order: 'asc' };
      if (employee) params.employee = employee;
      if (category) params.category = category;
      if (from) params.from = new Date(from).toISOString();
      if (to) params.to = new Date(to).toISOString();
      const { data } = await api.get('/api/staff/transcriptions/', { params });
      setRecords(unwrap<Segment>(data));
    } catch {
      setError('Не удалось загрузить ленту');
    } finally {
      setLoading(false);
    }
  }, [employee, category, from, to]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-8 flex flex-col h-screen">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-gray-800">Лента разговоров</h2>
        <p className="text-sm text-gray-500 mt-0.5">Запись по активации голоса — текст и оригинал аудио по времени</p>
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
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Категория</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
            <option value="">Все</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.title_display}</option>)}
          </select>
        </div>
        <button onClick={load}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md">
          Обновить
        </button>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>}

      {/* Чат-лента */}
      <div className="flex-1 overflow-y-auto bg-gray-50 rounded-lg border border-gray-200 p-4 space-y-3">
        {loading ? (
          <div className="text-center text-gray-400 py-12">Загрузка...</div>
        ) : records.length === 0 ? (
          <div className="text-center text-gray-400 py-12">За выбранный период записей нет</div>
        ) : records.map((r: Segment) => (
          <div key={r.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-3 max-w-3xl">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs font-mono text-gray-400">#{r.id}</span>
              <span className="text-xs font-semibold text-gray-700">{r.employee_name}</span>
              {r.category_title && (
                <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${catColor(r.category_title)}`}>
                  {r.category_title}
                </span>
              )}
              <span className="ml-auto text-xs text-gray-400">
                {new Date(r.record_datetime).toLocaleString('ru-RU')}
              </span>
            </div>
            <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed mb-2">
              {r.text || <span className="italic text-gray-400">(обрабатывается…)</span>}
            </div>
            {r.audio_url && (
              <audio controls preload="none" src={r.audio_url} className="w-full h-8" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

