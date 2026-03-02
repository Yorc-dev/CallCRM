import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import type { Client, Call } from '../api/types';

export default function ClientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [client, setClient] = useState<Client | null>(null);
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Editable fields
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [gender, setGender] = useState('');
  const [language, setLanguage] = useState('');
  const [tags, setTags] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/api/clients/${id}/`);
        setClient(data);
        setFullName(data.full_name ?? '');
        setPhone(data.phone ?? '');
        setGender(data.gender ?? '');
        setLanguage(data.language ?? '');
        setTags(data.tags?.join(', ') ?? '');

        // Fetch calls for this client
        const { data: callsData } = await api.get('/api/calls/', { params: { client: id } });
        setCalls(Array.isArray(callsData) ? callsData : callsData.results ?? []);
      } catch {
        setError('Failed to load client');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      const payload = {
        full_name: fullName,
        phone,
        gender: gender || undefined,
        language: language || undefined,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      };
      const { data } = await api.patch(`/api/clients/${id}/`, payload);
      setClient(data);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      setError('Failed to save client');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>;
  if (error && !client) return <div className="p-8 text-red-600">{error}</div>;
  if (!client) return null;

  return (
    <div className="p-8">
      <button onClick={() => navigate('/clients')}
        className="text-sm text-indigo-600 hover:text-indigo-800 mb-4 flex items-center gap-1">
        ← Back to Clients
      </button>

      <h2 className="text-2xl font-bold text-gray-800 mb-6">Client #{client.id}</h2>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>
      )}

      {/* Edit Form */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Client Information</h3>
        <form onSubmit={handleSave} className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              type="text"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option value="">Unknown</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
            <input
              type="text"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Tags (comma separated)</label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g. vip, loyal, new"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div className="col-span-2 flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors disabled:opacity-60"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
            {saveSuccess && <span className="text-green-600 text-sm">Saved successfully!</span>}
          </div>
        </form>
      </div>

      {/* Calls History */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800">Call History</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Operator</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Date/Time</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Duration</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {calls.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No calls found for this client</td>
              </tr>
            ) : (
              calls.map((call) => (
                <tr
                  key={call.id}
                  onClick={() => navigate(`/calls/${call.id}`)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-gray-700 font-mono">#{call.id}</td>
                  <td className="px-4 py-3 text-gray-600">{call.operator_detail?.username ?? `#${call.operator}`}</td>
                  <td className="px-4 py-3 text-gray-600">{new Date(call.started_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {call.duration ? `${Math.floor(call.duration / 60)}:${String(call.duration % 60).padStart(2, '0')}` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold capitalize ${
                      { new: 'bg-gray-500 text-gray-100', uploaded: 'bg-blue-600 text-blue-100', processing: 'bg-yellow-600 text-yellow-100', done: 'bg-green-700 text-green-100', failed: 'bg-red-700 text-red-100' }[call.status] ?? 'bg-gray-200 text-gray-700'
                    }`}>
                      {call.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
