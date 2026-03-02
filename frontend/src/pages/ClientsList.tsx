import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import type { Client } from '../api/types';

export default function ClientsList() {
  const navigate = useNavigate();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);

  // New client form state
  const [newName, setNewName] = useState('');
  const [newPhone, setNewPhone] = useState('');

  const fetchClients = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/clients/');
      setClients(Array.isArray(data) ? data : data.results ?? []);
    } catch {
      setError('Failed to load clients');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const { data } = await api.post('/api/clients/', { full_name: newName, phone: newPhone });
      setShowModal(false);
      setNewName('');
      setNewPhone('');
      navigate(`/clients/${data.id}`);
    } catch {
      setError('Failed to create client');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Clients</h2>
        <button
          onClick={() => setShowModal(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          + New Client
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Loading...</div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Phone</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Gender</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Language</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Tags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {clients.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-gray-400">No clients found</td>
                </tr>
              ) : (
                clients.map((client) => (
                  <tr
                    key={client.id}
                    onClick={() => navigate(`/clients/${client.id}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-700 font-mono">#{client.id}</td>
                    <td className="px-4 py-3 text-gray-800 font-medium">{client.full_name}</td>
                    <td className="px-4 py-3 text-gray-600">{client.phone}</td>
                    <td className="px-4 py-3 text-gray-600 capitalize">{client.gender ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{client.language ?? '—'}</td>
                    <td className="px-4 py-3">
                      {client.tags && client.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {client.tags.map((tag) => (
                            <span key={tag} className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs">{tag}</span>
                          ))}
                        </div>
                      ) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">New Client</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="text"
                  required
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={creating}
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium transition-colors disabled:opacity-60">
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
