import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import api from '../api/client';

interface Company {
  id: number;
  name: string;
}

interface Settings {
  mode: 'single' | 'multiple';
  mode_display: string;
}

interface Employee {
  id: number;
  full_name: string;
  email: string;
  company: number;
  company_name: string;
  group: number | null;
  group_name: string | null;
  username: string;
  user_role: string;
  certificate_expires_at: string | null;
  created_at: string;
}

interface Access {
  value: string;
  label: string;
}

interface Group {
  id: number;
  name: string;
  company: number;
  company_name: string;
  accesses: string[];
  available_accesses: Access[];
  employee_count: number;
  created_at: string;
}

type Tab = 'employees' | 'groups';

const ROLE_OPTIONS = [
  { value: 'operator', label: 'Оператор' },
  { value: 'chief', label: 'Руководитель' },
  { value: 'admin', label: 'Администратор' },
];

export default function Staff() {
  const [tab, setTab] = useState<Tab>('employees');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);

  const isSingle = settings?.mode === 'single';

  // --- Employees ---
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [empLoading, setEmpLoading] = useState(true);
  const [empSearch, setEmpSearch] = useState('');
  const [empCompanyFilter, setEmpCompanyFilter] = useState('');
  const [showEmpModal, setShowEmpModal] = useState(false);
  const [newFullName, setNewFullName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('operator');
  const [newCompanyId, setNewCompanyId] = useState('');
  const [newGroupId, setNewGroupId] = useState('');
  const [newCertExpires, setNewCertExpires] = useState('');
  const [creatingEmp, setCreatingEmp] = useState(false);

  // --- Groups ---
  const [groups, setGroups] = useState<Group[]>([]);
  const [grpLoading, setGrpLoading] = useState(true);
  const [availableAccesses, setAvailableAccesses] = useState<Access[]>([]);
  const [showGrpModal, setShowGrpModal] = useState(false);
  const [grpName, setGrpName] = useState('');
  const [grpCompanyId, setGrpCompanyId] = useState('');
  const [grpAccesses, setGrpAccesses] = useState<string[]>([]);
  const [creatingGrp, setCreatingGrp] = useState(false);

  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/api/staff/companies/').then((r) => setCompanies(r.data?.results ?? r.data ?? [])).catch(() => {});
    api.get('/api/staff/groups/available-accesses/').then((r) => setAvailableAccesses(r.data)).catch(() => {});
    api.get('/api/staff/settings/').then((r) => setSettings(r.data)).catch(() => {});
  }, []);

  const fetchEmployees = async () => {
    setEmpLoading(true);
    try {
      const params: Record<string, string> = {};
      if (empSearch) params.search = empSearch;
      if (empCompanyFilter) params.company = empCompanyFilter;
      const { data } = await api.get('/api/staff/employees/', { params });
      setEmployees(Array.isArray(data) ? data : data.results ?? []);
    } catch {
      setError('Не удалось загрузить сотрудников');
    } finally {
      setEmpLoading(false);
    }
  };

  const fetchGroups = async () => {
    setGrpLoading(true);
    try {
      const { data } = await api.get('/api/staff/groups/');
      setGroups(Array.isArray(data) ? data : data.results ?? []);
    } catch {
      setError('Не удалось загрузить группы');
    } finally {
      setGrpLoading(false);
    }
  };

  useEffect(() => { fetchEmployees(); }, [empSearch, empCompanyFilter]);
  useEffect(() => { fetchGroups(); }, []);

  // Группы для выбора в форме сотрудника — фильтруем по выбранной компании
  const employeeCompanyId = isSingle ? (companies[0]?.id?.toString() ?? '') : newCompanyId;
  const groupsForEmployee = groups.filter(
    (g) => !employeeCompanyId || g.company === parseInt(employeeCompanyId)
  );

  const openEmpModal = () => {
    setNewFullName(''); setNewEmail(''); setNewPassword('');
    setNewRole('operator'); setNewCompanyId(''); setNewGroupId(''); setNewCertExpires('');
    setShowEmpModal(true);
  };

  const openGrpModal = () => {
    setGrpName(''); setGrpCompanyId(''); setGrpAccesses([]);
    setShowGrpModal(true);
  };

  const handleCreateEmployee = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setCreatingEmp(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: newFullName,
        email: newEmail,
        password: newPassword,
        role: newRole,
      };
      // В режиме multiple компания обязательна; в single бэкенд подставит сам
      if (!isSingle && newCompanyId) payload.company = parseInt(newCompanyId);
      if (newGroupId) payload.group = parseInt(newGroupId);
      if (newCertExpires) payload.certificate_expires_at = newCertExpires;

      const { data } = await api.post('/api/staff/employees/', payload);
      setEmployees((prev) => [data, ...prev]);
      setShowEmpModal(false);
    } catch (err) {
      setError(extractError(err, 'Не удалось создать сотрудника'));
    } finally {
      setCreatingEmp(false);
    }
  };

  const handleCreateGroup = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setCreatingGrp(true);
    try {
      const companyId = isSingle ? companies[0]?.id : parseInt(grpCompanyId);
      const { data } = await api.post('/api/staff/groups/', {
        name: grpName,
        company: companyId,
        accesses: grpAccesses,
      });
      setGroups((prev) => [data, ...prev]);
      setShowGrpModal(false);
    } catch (err) {
      setError(extractError(err, 'Не удалось создать группу'));
    } finally {
      setCreatingGrp(false);
    }
  };

  // Инлайн-привязка сотрудника к группе прямо из таблицы
  const handleAssignGroup = async (empId: number, groupId: string) => {
    setError('');
    try {
      const { data } = await api.patch(`/api/staff/employees/${empId}/`, {
        group: groupId === '' ? null : parseInt(groupId),
      });
      setEmployees((prev) => prev.map((e) => (e.id === empId ? data : e)));
    } catch (err) {
      setError(extractError(err, 'Не удалось изменить группу'));
    }
  };

  const handleDeleteEmployee = async (id: number) => {
    if (!confirm('Удалить сотрудника?')) return;
    try {
      await api.delete(`/api/staff/employees/${id}/`);
      setEmployees((prev) => prev.filter((e) => e.id !== id));
    } catch { setError('Ошибка удаления'); }
  };

  const handleDeleteGroup = async (id: number) => {
    if (!confirm('Удалить группу?')) return;
    try {
      await api.delete(`/api/staff/groups/${id}/`);
      setGroups((prev) => prev.filter((g) => g.id !== id));
    } catch { setError('Ошибка удаления'); }
  };

  const toggleAccess = (value: string) => {
    setGrpAccesses((prev) =>
      prev.includes(value) ? prev.filter((a) => a !== value) : [...prev, value]
    );
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Сотрудники</h2>
        <button
          onClick={() => tab === 'employees' ? openEmpModal() : openGrpModal()}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          {tab === 'employees' ? '+ Новый сотрудник' : '+ Новая группа'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-0">
          {(['employees', 'groups'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {t === 'employees' ? 'Сотрудники' : 'Группы и доступы'}
            </button>
          ))}
        </nav>
      </div>

      {/* EMPLOYEES TAB */}
      {tab === 'employees' && (
        <>
          <div className="flex gap-3 mb-4">
            <input
              type="text"
              placeholder="Поиск по имени или email..."
              value={empSearch}
              onChange={(e) => setEmpSearch(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 w-64"
            />
            {!isSingle && (
              <select
                value={empCompanyFilter}
                onChange={(e) => setEmpCompanyFilter(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              >
                <option value="">Все компании</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>
          {empLoading ? (
            <div className="text-center text-gray-500 py-12">Загрузка...</div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ФИО</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Email</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Логин</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Группа</th>
                    {!isSingle && <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Компания</th>}
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Сертификат до</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {employees.length === 0 ? (
                    <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-400">Сотрудники не найдены</td></tr>
                  ) : employees.map((emp) => (
                    <tr key={emp.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-700 font-mono">#{emp.id}</td>
                      <td className="px-4 py-3 text-gray-800 font-medium">{emp.full_name}</td>
                      <td className="px-4 py-3 text-gray-600">{emp.email}</td>
                      <td className="px-4 py-3 text-gray-600 font-mono">{emp.username}</td>
                      <td className="px-4 py-3">
                        <select
                          value={emp.group ?? ''}
                          onChange={(e) => handleAssignGroup(emp.id, e.target.value)}
                          className="border border-gray-200 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
                        >
                          <option value="">— Без группы —</option>
                          {groups
                            .filter((g) => g.company === emp.company)
                            .map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                        </select>
                      </td>
                      {!isSingle && (
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs">{emp.company_name}</span>
                        </td>
                      )}
                      <td className="px-4 py-3 text-gray-500">
                        {emp.certificate_expires_at
                          ? new Date(emp.certificate_expires_at).toLocaleDateString('ru-RU')
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => handleDeleteEmployee(emp.id)}
                          className="text-xs text-red-500 hover:text-red-700">Удалить</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* GROUPS TAB */}
      {tab === 'groups' && (
        grpLoading ? (
          <div className="text-center text-gray-500 py-12">Загрузка...</div>
        ) : (
          <div className="space-y-4">
            {groups.length === 0 ? (
              <div className="text-center text-gray-400 py-12">Группы не найдены</div>
            ) : groups.map((g) => (
              <div key={g.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-800">{g.name}</h3>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {!isSingle && <>Компания: <span className="text-gray-700">{g.company_name}</span> · </>}
                      Сотрудников: <span className="text-gray-700">{g.employee_count}</span>
                    </p>
                  </div>
                  <button onClick={() => handleDeleteGroup(g.id)}
                    className="text-xs text-red-500 hover:text-red-700">Удалить</button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {g.accesses.length === 0 ? (
                    <span className="text-xs text-gray-400 italic">Нет доступов</span>
                  ) : g.accesses.map((a) => {
                    const label = availableAccesses.find((x) => x.value === a)?.label ?? a;
                    return (
                      <span key={a} className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                        {label}
                      </span>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Create Employee Modal */}
      {showEmpModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Новый сотрудник</h3>
            <form onSubmit={handleCreateEmployee} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ФИО</label>
                <input type="text" required value={newFullName} onChange={(e) => setNewFullName(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="Иванов Иван Иванович" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="ivan@example.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
                <input type="password" required minLength={6} value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="Минимум 6 символов" />
                <p className="text-xs text-gray-400 mt-1">Пользователь создаётся автоматически. Логин — из email.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Роль</label>
                <select value={newRole} onChange={(e) => setNewRole(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                  {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              {!isSingle && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Компания</label>
                  <select required value={newCompanyId} onChange={(e) => { setNewCompanyId(e.target.value); setNewGroupId(''); }}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                    <option value="">Выберите компанию</option>
                    {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Группа <span className="text-gray-400">(необязательно)</span></label>
                <select value={newGroupId} onChange={(e) => setNewGroupId(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                  <option value="">— Без группы —</option>
                  {groupsForEmployee.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Сертификат действует до <span className="text-gray-400">(необязательно)</span></label>
                <input type="date" value={newCertExpires} onChange={(e) => setNewCertExpires(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => setShowEmpModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">Отмена</button>
                <button type="submit" disabled={creatingEmp}
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium disabled:opacity-60">
                  {creatingEmp ? 'Создание...' : 'Создать'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Group Modal */}
      {showGrpModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Новая группа</h3>
            <form onSubmit={handleCreateGroup} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Название группы</label>
                <input type="text" required value={grpName} onChange={(e) => setGrpName(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="Менеджеры" />
              </div>
              {!isSingle && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Компания</label>
                  <select required value={grpCompanyId} onChange={(e) => setGrpCompanyId(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
                    <option value="">Выберите компанию</option>
                    {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Доступы</label>
                <div className="grid grid-cols-2 gap-2">
                  {availableAccesses.map((a) => (
                    <label key={a.value} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={grpAccesses.includes(a.value)}
                        onChange={() => toggleAccess(a.value)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-400"
                      />
                      <span className="text-sm text-gray-700">{a.label}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => setShowGrpModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">Отмена</button>
                <button type="submit" disabled={creatingGrp}
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium disabled:opacity-60">
                  {creatingGrp ? 'Создание...' : 'Создать'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
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
