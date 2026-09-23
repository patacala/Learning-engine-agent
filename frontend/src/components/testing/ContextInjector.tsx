import { useState } from 'react';
import type { Scenario, TemporaryDocument } from '../../types/testing';
import { SCENARIO_TEMPLATES, type ScenarioTemplate } from '../../constants/testingTemplates';
import { DocumentCard } from './DocumentCard';

interface Props {
  scenarios: Scenario[];
  selectedScenarioId: string | null;
  scenarioName: string;
  companyName: string;
  documents: TemporaryDocument[];
  quickFacts: Record<string, string>;
  onScenarioNameChange: (v: string) => void;
  onCompanyNameChange: (v: string) => void;
  onNewScenario: () => void;
  onLoadScenario: (s: Scenario) => void;
  onDeleteScenario: (id: string) => void;
  onApplyTemplate: (t: ScenarioTemplate) => void;
  onAddDocument: () => void;
  onUpdateDocument: (id: string, patch: Partial<TemporaryDocument>) => void;
  onRemoveDocument: (id: string) => void;
  onSetQuickFact: (key: string, value: string) => void;
  onRemoveQuickFact: (key: string) => void;
  onSaveScenario: () => void;
}

export function ContextInjector(props: Props) {
  const [factKey, setFactKey] = useState('');
  const [factValue, setFactValue] = useState('');

  const addFact = () => {
    if (!factKey.trim()) return;
    props.onSetQuickFact(factKey.trim(), factValue.trim());
    setFactKey('');
    setFactValue('');
  };

  return (
    <div className="w-[340px] flex-shrink-0 border-l border-[#ececec] flex flex-col h-full bg-[#fafafa]">
      <div className="px-4 py-3 border-b border-[#ececec] flex items-center justify-between">
        <span className="text-[14px] font-semibold text-[#0d0d0d]">Business context</span>
        <button
          onClick={props.onNewScenario}
          className="text-[12px] text-[#6e6e80] hover:text-[#0d0d0d] transition-colors"
        >
          New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* Saved scenarios */}
        {props.scenarios.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1.5">
              Saved scenarios
            </p>
            <div className="space-y-1">
              {props.scenarios.map((s) => (
                <div
                  key={s.id}
                  className={`group flex items-center gap-1.5 rounded-md px-2 py-1.5 cursor-pointer transition-colors ${
                    props.selectedScenarioId === s.id ? 'bg-[#ececec]' : 'hover:bg-[#f0f0f0]'
                  }`}
                  onClick={() => props.onLoadScenario(s)}
                >
                  <span className="flex-1 min-w-0 text-[12px] text-[#0d0d0d] truncate">
                    {s.name}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      props.onDeleteScenario(s.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-[#b3b3b3] hover:text-[#0d0d0d] transition-opacity"
                    title="Remove"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Templates */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1.5">Templates</p>
          <div className="flex flex-wrap gap-1.5">
            {SCENARIO_TEMPLATES.map((t) => (
              <button
                key={t.id}
                onClick={() => props.onApplyTemplate(t)}
                className="text-[11px] text-[#6e6e80] border border-[#e3e3e3] rounded-full px-2.5 py-1 hover:bg-[#ececec] hover:text-[#0d0d0d] transition-colors"
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Scenario / company name */}
        <div className="space-y-2">
          <input
            value={props.scenarioName}
            onChange={(e) => props.onScenarioNameChange(e.target.value)}
            placeholder="Scenario name"
            className="w-full text-[13px] text-[#0d0d0d] bg-white border border-[#e3e3e3] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#b3b3b3]"
          />
          <input
            value={props.companyName}
            onChange={(e) => props.onCompanyNameChange(e.target.value)}
            placeholder="Company (e.g. Audi Center)"
            className="w-full text-[13px] text-[#0d0d0d] bg-white border border-[#e3e3e3] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#b3b3b3]"
          />
        </div>

        {/* Quick facts */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3] mb-1.5">Quick facts</p>
          <div className="space-y-1 mb-2">
            {Object.entries(props.quickFacts).map(([k, v]) => (
              <div key={k} className="flex items-center gap-1.5 text-[12px]">
                <span className="text-[#6e6e80] flex-shrink-0">{k}:</span>
                <span className="text-[#0d0d0d] flex-1 min-w-0 truncate">{v}</span>
                <button
                  onClick={() => props.onRemoveQuickFact(k)}
                  className="text-[#b3b3b3] hover:text-[#0d0d0d]"
                  title="Eliminar"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <input
              value={factKey}
              onChange={(e) => setFactKey(e.target.value)}
              placeholder="key"
              className="w-[38%] text-[12px] bg-white border border-[#e3e3e3] rounded-md px-2 py-1 focus:outline-none focus:border-[#b3b3b3]"
            />
            <input
              value={factValue}
              onChange={(e) => setFactValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addFact()}
              placeholder="value"
              className="flex-1 min-w-0 text-[12px] bg-white border border-[#e3e3e3] rounded-md px-2 py-1 focus:outline-none focus:border-[#b3b3b3]"
            />
            <button
              onClick={addFact}
              className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-md bg-[#ececec] text-[#0d0d0d] hover:bg-[#e3e3e3] transition-colors"
              title="Add fact"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </div>
        </div>

        {/* Documents */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-[10px] uppercase tracking-wider text-[#b3b3b3]">Documents</p>
            <button
              onClick={props.onAddDocument}
              className="text-[11px] text-[#6e6e80] hover:text-[#0d0d0d] transition-colors"
            >
              + Add
            </button>
          </div>
          <div className="space-y-2">
            {props.documents.length === 0 && (
              <p className="text-[12px] text-[#b3b3b3] py-2 text-center">
                Add products, prices or policies
              </p>
            )}
            {props.documents.map((doc) => (
              <DocumentCard
                key={doc.id}
                doc={doc}
                onChange={(patch) => props.onUpdateDocument(doc.id, patch)}
                onRemove={() => props.onRemoveDocument(doc.id)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="px-4 py-3 border-t border-[#ececec]">
        <button
          onClick={props.onSaveScenario}
          className="w-full text-[13px] font-medium text-white bg-[#0d0d0d] rounded-lg py-2 hover:bg-[#1a1a1a] transition-colors"
        >
          {props.selectedScenarioId ? 'Update scenario' : 'Save scenario'}
        </button>
      </div>
    </div>
  );
}
