import { useState, useEffect, useCallback } from 'react';
import type { FormEvent, ReactNode } from 'react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';

// --------------------------------------------------------------------------- //
//  Типы конфигурации
// --------------------------------------------------------------------------- //
type FieldType =
  | 'text' | 'email' | 'password' | 'number'
  | 'date' | 'datetime' | 'textarea' | 'select' | 'multiselect'
  | 'boolean' | 'flags';

interface FieldOption { value: string | number; label: string; }

interface Field {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  createOnly?: boolean;          // показывать только при создании (пароль)
  options?: FieldOption[];       // статичные опции
  lookup?: LookupKey;            // динамические опции из справочника
  lookupLabel?: (item: Row) => string;
  hint?: string;
}

interface Column {
  key: string;
  label: string;
  render?: (row: Row) => ReactNode;
}

interface Resource {
  key: string;
  endpoint: string;
  title: string;
  columns: Column[];
  fields: Field[];
  canCreate?: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
}

type Row = Record<string, unknown>;
type LookupKey = 'companies' | 'groups' | 'employees' | 'records' | 'accesses' | 'plans' | 'departments';

function unwrap(data: unknown): Row[] {
  if (Array.isArray(data)) return data as Row[];
  return ((data as { results?: Row[] })?.results) ?? [];
}

const ROLE_OPTIONS: FieldOption[] = [
  { value: 'operator', label: 'Оператор' },
  { value: 'chief', label: 'Руководитель' },
  { value: 'admin', label: 'Администратор' },
];

const CATEGORY_OPTIONS: FieldOption[] = [
  { value: 'work_moments', label: 'Рабочие моменты' },
  { value: 'negotiations', label: 'Переговоры' },
];

function fmtDate(v: unknown): string {
  if (!v) return '—';
  const d = new Date(v as string);
  return isNaN(d.getTime()) ? String(v) : d.toLocaleString('ru-RU');
}

// --------------------------------------------------------------------------- //
//  Главный компонент
// --------------------------------------------------------------------------- //
export default function Management() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  // Справочники для динамических select'ов
  const [lookups, setLookups] = useState<Record<LookupKey, Row[]>>({
    companies: [], groups: [], employees: [], records: [], accesses: [], plans: [], departments: [],
  });

  const loadLookups = useCallback(async () => {
    const [companies, groups, employees, records, accessesResp, plans, departments] = await Promise.all([
      api.get('/api/staff/companies/').then((r) => unwrap(r.data)).catch(() => []),
      api.get('/api/staff/groups/').then((r) => unwrap(r.data)).catch(() => []),
      api.get('/api/staff/employees/').then((r) => unwrap(r.data)).catch(() => []),
      api.get('/api/staff/transcriptions/').then((r) => unwrap(r.data)).catch(() => []),
      api.get('/api/staff/groups/available-accesses/').then((r) => r.data as Row[]).catch(() => []),
      api.get('/api/billing/plans/').then((r) => unwrap(r.data)).catch(() => []),
      api.get('/api/analysis/departments/').then((r) => unwrap(r.data)).catch(() => []),
    ]);
    setLookups({ companies, groups, employees, records, accesses: accessesResp, plans, departments });
  }, []);

  useEffect(() => { loadLookups(); }, [loadLookups]);

  // Конфигурация ресурсов
  const resources: Resource[] = [
    {
      key: 'companies', endpoint: '/api/staff/companies/', title: 'Компании',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'name', label: 'Название' },
        { key: 'plan_name', label: 'Пакет', render: (r) => (r.plan_name as string) ?? '—' },
        { key: 'users', label: 'Польз./лимит', render: (r) => `${r.user_count ?? 0}/${r.max_users ?? '∞'}` },
        { key: 'created_at', label: 'Создана', render: (r) => fmtDate(r.created_at) },
      ],
      fields: [
        { name: 'name', label: 'Название', type: 'text', required: true },
        { name: 'plan', label: 'Тарифный пакет', type: 'select', lookup: 'plans', lookupLabel: (p) => p.name as string },
      ],
    },
    {
      key: 'employees', endpoint: '/api/staff/employees/', title: 'Сотрудники',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'full_name', label: 'ФИО' },
        { key: 'email', label: 'Email' },
        { key: 'username', label: 'Логин' },
        { key: 'company_name', label: 'Компания' },
        { key: 'group_name', label: 'Группа', render: (r) => (r.group_name as string) ?? '—' },
        { key: 'department_name', label: 'Отдел', render: (r) => (r.department_name as string) ?? '—' },
        { key: 'certificate_expires_at', label: 'Сертификат до', render: (r) => r.certificate_expires_at ? new Date(r.certificate_expires_at as string).toLocaleDateString('ru-RU') : '—' },
      ],
      fields: [
        { name: 'full_name', label: 'ФИО', type: 'text', required: true },
        { name: 'email', label: 'Email', type: 'email', required: true },
        { name: 'password', label: 'Пароль', type: 'password', required: true, createOnly: true, hint: 'Пользователь создаётся автоматически' },
        { name: 'role', label: 'Роль', type: 'select', options: ROLE_OPTIONS },
        { name: 'company', label: 'Компания', type: 'select', required: true, lookup: 'companies', lookupLabel: (c) => c.name as string },
        { name: 'group', label: 'Группа', type: 'select', lookup: 'groups', lookupLabel: (g) => g.name as string },
        { name: 'department', label: 'Отдел', type: 'select', lookup: 'departments', lookupLabel: (d) => d.name as string },
        { name: 'certificate_expires_at', label: 'Сертификат действует до', type: 'date' },
      ],
    },
    {
      key: 'groups', endpoint: '/api/staff/groups/', title: 'Группы и доступы',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'name', label: 'Название' },
        { key: 'company_name', label: 'Компания' },
        { key: 'employee_count', label: 'Сотрудников' },
        { key: 'accesses', label: 'Доступы', render: (r) => (
          <div className="flex flex-wrap gap-1">
            {(r.accesses as string[]).map((a) => (
              <span key={a} className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs">{a}</span>
            ))}
          </div>
        ) },
      ],
      fields: [
        { name: 'name', label: 'Название группы', type: 'text', required: true },
        { name: 'company', label: 'Компания', type: 'select', required: true, lookup: 'companies', lookupLabel: (c) => c.name as string },
        { name: 'accesses', label: 'Доступы', type: 'multiselect', lookup: 'accesses' },
      ],
    },
    {
      key: 'categories', endpoint: '/api/staff/categories/', title: 'Категории',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'title_display', label: 'Категория' },
      ],
      fields: [{ name: 'title', label: 'Категория', type: 'select', required: true, options: CATEGORY_OPTIONS }],
    },
    {
      key: 'incidents', endpoint: '/api/staff/incidents/', title: 'Инциденты',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'employee_name', label: 'Сотрудник' },
        { key: 'company_name', label: 'Компания' },
        { key: 'segment', label: 'Отрезок', render: (r) => `${r.start_minutes}–${r.end_minutes} мин` },
        { key: 'record', label: 'Запись', render: (r) => `#${r.record}` },
        { key: 'record_datetime', label: 'Дата записи', render: (r) => fmtDate(r.record_datetime) },
      ],
      fields: [
        { name: 'record', label: 'Запись', type: 'select', required: true, lookup: 'records', lookupLabel: (r) => `#${r.id} — ${r.employee_name}` },
        { name: 'analysis', label: 'Анализ (необязательно)', type: 'number' },
        { name: 'start_minutes', label: 'Начало (мин)', type: 'number', required: true },
        { name: 'end_minutes', label: 'Конец (мин)', type: 'number', required: true },
      ],
    },
    {
      key: 'plans', endpoint: '/api/billing/plans/', title: 'Пакеты',
      canCreate: isAdmin, canEdit: isAdmin, canDelete: isAdmin,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'name', label: 'Название' },
        { key: 'max_users', label: 'Макс. польз.', render: (r) => (r.max_users != null ? String(r.max_users) : '∞') },
        { key: 'price', label: 'Цена' },
        { key: 'company_count', label: 'Компаний' },
        { key: 'is_active', label: 'Активен', render: (r) => (r.is_active ? 'Да' : 'Нет') },
      ],
      fields: [
        { name: 'name', label: 'Название', type: 'text', required: true },
        { name: 'description', label: 'Описание', type: 'textarea' },
        { name: 'max_users', label: 'Макс. пользователей (пусто = ∞)', type: 'number' },
        { name: 'price', label: 'Цена', type: 'number' },
        { name: 'features', label: 'Функции пакета', type: 'flags', options: [
          { value: 'analytics', label: 'Аналитика' },
          { value: 'dynamic_prompts', label: 'Динамические промпты' },
        ] },
        { name: 'is_active', label: 'Активен', type: 'boolean' },
      ],
    },
    {
      key: 'departments', endpoint: '/api/analysis/departments/', title: 'Отделы',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'name', label: 'Название' },
        { key: 'company_name', label: 'Компания' },
        { key: 'employee_count', label: 'Сотрудников' },
        { key: 'is_active', label: 'Активен', render: (r) => (r.is_active ? 'Да' : 'Нет') },
      ],
      fields: [
        { name: 'name', label: 'Название отдела', type: 'text', required: true },
        { name: 'company', label: 'Компания', type: 'select', required: true, lookup: 'companies', lookupLabel: (c) => c.name as string },
        { name: 'description', label: 'Описание', type: 'textarea' },
        { name: 'is_active', label: 'Активен', type: 'boolean' },
      ],
    },
    {
      key: 'analysis_settings', endpoint: '/api/analysis/settings/', title: 'Настройки анализа',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'company_name', label: 'Компания' },
        { key: 'enabled', label: 'AI-анализ', render: (r) => (r.enabled ? 'Включён' : 'Выключен') },
      ],
      fields: [
        { name: 'company', label: 'Компания', type: 'select', required: true, lookup: 'companies', lookupLabel: (c) => c.name as string },
        { name: 'enabled', label: 'Включить AI-анализ разговоров', type: 'boolean' },
      ],
    },
    {
      key: 'criteria', endpoint: '/api/analysis/criteria/', title: 'Критерии (промпты)',
      canCreate: true, canEdit: true, canDelete: true,
      columns: [
        { key: 'id', label: 'ID', render: (r) => `#${r.id}` },
        { key: 'name', label: 'Критерий' },
        { key: 'scope', label: 'Применять к', render: (r) =>
          (r.department_name as string) ? `Отдел: ${r.department_name}`
          : (r.group_name as string) ? `Группа: ${r.group_name}`
          : 'Все' },
        { key: 'company_name', label: 'Компания' },
        { key: 'enabled', label: 'Вкл', render: (r) => (r.enabled ? '✓' : '—') },
        { key: 'order', label: 'Порядок' },
      ],
      fields: [
        { name: 'name', label: 'Название критерия', type: 'text', required: true },
        { name: 'prompt_text', label: 'Промпт (инструкция модели)', type: 'textarea', required: true },
        { name: 'company', label: 'Компания', type: 'select', required: true, lookup: 'companies', lookupLabel: (c) => c.name as string },
        { name: 'department', label: 'Отдел (или оставьте пустым)', type: 'select', lookup: 'departments', lookupLabel: (d) => d.name as string, hint: 'Заполните отдел ИЛИ группу. Оба пустые = ко всем.' },
        { name: 'group', label: 'Группа (или оставьте пустым)', type: 'select', lookup: 'groups', lookupLabel: (g) => g.name as string },
        { name: 'order', label: 'Порядок', type: 'number' },
        { name: 'enabled', label: 'Включён', type: 'boolean' },
      ],
    },
  ];

  const [activeKey, setActiveKey] = useState(resources[0].key);
  const active = resources.find((r) => r.key === activeKey)!;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Управление</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          {isAdmin ? 'Полный доступ ко всем данным' : 'Данные вашей компании'}
        </p>
      </div>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-0 flex-wrap">
          {resources.map((r) => (
            <button key={r.key} onClick={() => setActiveKey(r.key)}
              className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeKey === r.key ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}>
              {r.title}
            </button>
          ))}
        </nav>
      </div>

      <CrudResource
        key={active.key}
        resource={active}
        lookups={lookups}
        onMutated={loadLookups}
      />
    </div>
  );
}

// --------------------------------------------------------------------------- //
//  Универсальный CRUD по ресурсу
// --------------------------------------------------------------------------- //
function CrudResource({ resource, lookups, onMutated }: {
  resource: Resource;
  lookups: Record<LookupKey, Row[]>;
  onMutated: () => void;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState<{ mode: 'create' | 'edit'; row: Row | null } | null>(null);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(resource.endpoint);
      setRows(unwrap(data));
    } catch {
      setError('Не удалось загрузить данные');
    } finally {
      setLoading(false);
    }
  }, [resource.endpoint]);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  const handleDelete = async (id: unknown) => {
    if (!confirm('Удалить запись?')) return;
    try {
      await api.delete(`${resource.endpoint}${id}/`);
      setRows((prev) => prev.filter((r) => r.id !== id));
      onMutated();
    } catch { setError('Ошибка удаления'); }
  };

  const optionsFor = (f: Field): FieldOption[] => {
    if (f.options) return f.options;
    if (f.lookup) {
      return lookups[f.lookup].map((item) => ({
        value: (item.value ?? item.id) as string | number,
        label: f.lookupLabel ? f.lookupLabel(item) : String(item.label ?? item.id),
      }));
    }
    return [];
  };

  return (
    <div>
      <div className="flex justify-end mb-4">
        {resource.canCreate && (
          <button onClick={() => setModal({ mode: 'create', row: null })}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md">
            + Создать
          </button>
        )}
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Загрузка...</div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {resource.columns.map((c) => (
                  <th key={c.key} className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide whitespace-nowrap">{c.label}</th>
                ))}
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.length === 0 ? (
                <tr><td colSpan={resource.columns.length + 1} className="px-4 py-12 text-center text-gray-400">Нет данных</td></tr>
              ) : rows.map((row) => (
                <tr key={String(row.id)} className="hover:bg-gray-50">
                  {resource.columns.map((c) => (
                    <td key={c.key} className="px-4 py-3 text-gray-700">
                      {c.render ? c.render(row) : (row[c.key] != null ? String(row[c.key]) : '—')}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {resource.canEdit && (
                      <button onClick={() => setModal({ mode: 'edit', row })}
                        className="text-xs text-indigo-600 hover:text-indigo-800 mr-3">Изменить</button>
                    )}
                    {resource.canDelete && (
                      <button onClick={() => handleDelete(row.id)}
                        className="text-xs text-red-500 hover:text-red-700">Удалить</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <CrudModal
          resource={resource}
          mode={modal.mode}
          row={modal.row}
          optionsFor={optionsFor}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); fetchRows(); onMutated(); }}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
//  Модальное окно создания/редактирования
// --------------------------------------------------------------------------- //
function CrudModal({ resource, mode, row, optionsFor, onClose, onSaved }: {
  resource: Resource;
  mode: 'create' | 'edit';
  row: Row | null;
  optionsFor: (f: Field) => FieldOption[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const visibleFields = resource.fields.filter((f) => mode === 'create' || !f.createOnly);

  const initial: Row = {};
  for (const f of visibleFields) {
    if (mode === 'edit' && row) {
      if (f.type === 'multiselect') initial[f.name] = row[f.name] ?? [];
      else if (f.type === 'flags') initial[f.name] = row[f.name] ?? {};
      else if (f.type === 'boolean') initial[f.name] = row[f.name] ?? false;
      else initial[f.name] = row[f.name] ?? '';
    } else {
      if (f.type === 'multiselect') initial[f.name] = [];
      else if (f.type === 'flags') initial[f.name] = {};
      else if (f.type === 'boolean') initial[f.name] = true;
      else initial[f.name] = f.type === 'select' && f.options?.[0] ? f.options[0].value : '';
    }
  }

  const [values, setValues] = useState<Row>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setVal = (name: string, v: unknown) => setValues((prev) => ({ ...prev, [name]: v }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload: Row = {};
      for (const f of visibleFields) {
        const v = values[f.name];
        if (f.type === 'multiselect') { payload[f.name] = v ?? []; continue; }
        if (f.type === 'flags') { payload[f.name] = v ?? {}; continue; }
        if (f.type === 'boolean') { payload[f.name] = Boolean(v); continue; }
        if (v === '' || v == null) {
          if (f.required) { setError(`Заполните поле «${f.label}»`); setSaving(false); return; }
          continue; // не отправляем пустые необязательные
        }
        if (f.type === 'number') payload[f.name] = parseFloat(v as string);
        else payload[f.name] = v;
      }

      if (mode === 'create') await api.post(resource.endpoint, payload);
      else await api.patch(`${resource.endpoint}${row!.id}/`, payload);
      onSaved();
    } catch (err) {
      setError(extractError(err, 'Не удалось сохранить'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          {mode === 'create' ? `Создать: ${resource.title}` : `Изменить: ${resource.title}`}
        </h3>
        {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-3">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          {visibleFields.map((f) => (
            <div key={f.name}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {f.label}{f.required && <span className="text-red-500"> *</span>}
              </label>
              <FieldInput field={f} value={values[f.name]} options={optionsFor(f)} onChange={(v) => setVal(f.name, v)} />
              {f.hint && <p className="text-xs text-gray-400 mt-1">{f.hint}</p>}
            </div>
          ))}
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">Отмена</button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium disabled:opacity-60">
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FieldInput({ field, value, options, onChange }: {
  field: Field;
  value: unknown;
  options: FieldOption[];
  onChange: (v: unknown) => void;
}) {
  const base = 'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400';

  if (field.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)}
          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-400 w-4 h-4" />
        <span className="text-sm text-gray-600">{Boolean(value) ? 'Включено' : 'Выключено'}</span>
      </label>
    );
  }

  if (field.type === 'flags') {
    const obj = (value as Record<string, boolean>) ?? {};
    const toggle = (k: string) => onChange({ ...obj, [k]: !obj[k] });
    return (
      <div className="grid grid-cols-1 gap-2">
        {options.map((o) => (
          <label key={o.value} className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={Boolean(obj[o.value])} onChange={() => toggle(String(o.value))}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-400" />
            <span className="text-sm text-gray-700">{o.label}</span>
          </label>
        ))}
      </div>
    );
  }

  if (field.type === 'multiselect') {
    const selected = (value as (string | number)[]) ?? [];
    const toggle = (v: string | number) =>
      onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);
    return (
      <div className="grid grid-cols-2 gap-2">
        {options.map((o) => (
          <label key={o.value} className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={selected.includes(o.value)} onChange={() => toggle(o.value)}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-400" />
            <span className="text-sm text-gray-700">{o.label}</span>
          </label>
        ))}
      </div>
    );
  }

  if (field.type === 'select') {
    return (
      <select className={base} value={String(value ?? '')} required={field.required}
        onChange={(e) => onChange(e.target.value)}>
        <option value="">— Выберите —</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  }

  if (field.type === 'textarea') {
    return <textarea className={`${base} resize-none`} rows={3} value={String(value ?? '')}
      onChange={(e) => onChange(e.target.value)} />;
  }

  const inputType = field.type === 'datetime' ? 'datetime-local' : field.type;
  return (
    <input type={inputType} className={base} value={String(value ?? '')} required={field.required}
      step={field.type === 'number' ? '0.1' : undefined}
      onChange={(e) => onChange(e.target.value)} />
  );
}

// Извлекает текст ошибки из ответа DRF
function extractError(err: unknown, fallback: string): string {
  const resp = (err as { response?: { data?: unknown } })?.response?.data;
  if (resp && typeof resp === 'object') {
    const parts: string[] = [];
    for (const [key, val] of Object.entries(resp as Record<string, unknown>)) {
      const msg = Array.isArray(val) ? val.join(', ') : String(val);
      parts.push(key === 'detail' || key === 'non_field_errors' ? msg : `${key}: ${msg}`);
    }
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}
