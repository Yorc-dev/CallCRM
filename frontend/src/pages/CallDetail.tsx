import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import type { Call, CallAnalysis } from '../api/types';
import AudioPlayer from '../components/AudioPlayer';

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-gray-500 text-gray-100',
  uploaded: 'bg-blue-600 text-blue-100',
  processing: 'bg-yellow-600 text-yellow-100',
  done: 'bg-green-700 text-green-100',
  failed: 'bg-red-700 text-red-100',
};

type Tab = 'recording' | 'transcript' | 'analysis' | 'client_draft';

export default function CallDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [call, setCall] = useState<Call | null>(null);
  const [analysis, setAnalysis] = useState<CallAnalysis | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('recording');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [applyingDraft, setApplyingDraft] = useState(false);

  const fetchCall = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/api/calls/${id}/`);
      setCall(data);
      try {
        const { data: analysisData } = await api.get(`/api/calls/${id}/analysis/`);
        setAnalysis(analysisData);
      } catch {
        // no analysis yet
      }
    } catch {
      setError('Failed to load call');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCall();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      await api.post(`/api/calls/${id}/analyze/`);
      await fetchCall();
    } catch {
      setError('Failed to start analysis');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleApplyDraft = async () => {
    setApplyingDraft(true);
    try {
      await api.post(`/api/calls/${id}/confirm-client/`);
      await fetchCall();
    } catch {
      setError('Failed to apply client draft');
    } finally {
      setApplyingDraft(false);
    }
  };

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">{error}</div>;
  if (!call) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'recording', label: 'Recording' },
    { key: 'transcript', label: 'Transcript' },
    { key: 'analysis', label: 'Analysis' },
    { key: 'client_draft', label: 'Client Draft' },
  ];

  return (
    <div className="p-8">
      <button onClick={() => navigate('/calls')}
        className="text-sm text-indigo-600 hover:text-indigo-800 mb-4 flex items-center gap-1">
        ← Back to Calls
      </button>

      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-1">Call #{call.id}</h2>
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <span>Client: {call.client_detail?.full_name ?? (call.client ? `#${call.client}` : 'Unknown')}</span>
              <span>Operator: {call.operator_detail?.username ?? `#${call.operator}`}</span>
              <span>Started: {new Date(call.started_at).toLocaleString()}</span>
              {call.duration && <span>Duration: {Math.floor(call.duration / 60)}:{String(call.duration % 60).padStart(2, '0')}</span>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-semibold capitalize ${STATUS_COLORS[call.status]}`}>
              {call.status}
            </span>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors disabled:opacity-60"
            >
              {analyzing ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
        </div>
        {call.category && (
          <p className="mt-2 text-sm text-gray-500">Category: <span className="font-medium text-gray-700">{call.category}</span></p>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {activeTab === 'recording' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Recording</h3>
            {call.recording ? (
              <AudioPlayer src={call.recording.file} />
            ) : (
              <div className="text-center py-8">
                <p className="text-gray-500">No recording uploaded</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'transcript' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Transcript</h3>
            {analysis?.transcript_text ? (
              <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 rounded-md p-4 leading-relaxed">
                {analysis.transcript_text}
              </pre>
            ) : (
              <p className="text-gray-400 italic">Analysis not yet run</p>
            )}
          </div>
        )}

        {activeTab === 'analysis' && (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold text-gray-800">Analysis</h3>

            {!analysis ? (
              <p className="text-gray-400 italic">Analysis not yet run</p>
            ) : (
              <>
                {/* Summary Short */}
                {analysis.summary_short && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">Summary</h4>
                    <p className="text-sm text-gray-600 bg-gray-50 rounded-md p-4">{analysis.summary_short}</p>
                  </div>
                )}

                {/* Summary Structured */}
                {analysis.summary_structured && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">Structured Summary</h4>
                    <pre className="text-xs text-gray-600 bg-gray-50 rounded-md p-4 overflow-x-auto">
                      {JSON.stringify(analysis.summary_structured, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Script Compliance */}
                {analysis.script_compliance && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">
                      Script Compliance
                      {analysis.script_score !== undefined && (
                        <span className="ml-2 text-indigo-600">Score: {analysis.script_score}%</span>
                      )}
                    </h4>
                    <ul className="space-y-2">
                      {Object.entries(analysis.script_compliance).map(([step, passed]) => (
                        <li key={step} className="flex items-center gap-2 text-sm">
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {passed ? '✓' : '✗'}
                          </span>
                          <span className={passed ? 'text-gray-700' : 'text-gray-400'}>{step}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Operator Coaching */}
                {analysis.operator_coaching && analysis.operator_coaching.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">Operator Coaching</h4>
                    <div className="space-y-2">
                      {analysis.operator_coaching.map((tip, i) => (
                        <div key={i} className="flex gap-3 bg-amber-50 border border-amber-200 rounded-md p-3">
                          <span className="text-amber-500 mt-0.5">💡</span>
                          <p className="text-sm text-amber-800">{tip}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === 'client_draft' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-800">Client Draft</h3>
              {analysis?.client_draft && (
                <button
                  onClick={handleApplyDraft}
                  disabled={applyingDraft}
                  className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors disabled:opacity-60"
                >
                  {applyingDraft ? 'Applying...' : 'Apply Draft'}
                </button>
              )}
            </div>

            {analysis?.client_draft ? (
              <div className="bg-gray-50 rounded-md p-4">
                <dl className="grid grid-cols-2 gap-4">
                  {Object.entries(analysis.client_draft).map(([key, value]) => (
                    <div key={key}>
                      <dt className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{key.replace(/_/g, ' ')}</dt>
                      <dd className="text-sm text-gray-700 mt-1">{String(value ?? '—')}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : (
              <p className="text-gray-400 italic">No client draft available. Run analysis first.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
