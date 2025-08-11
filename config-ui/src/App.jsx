import React, { useMemo, useState, useEffect } from 'react'
import { Download, Upload, CheckCircle2, XCircle, Plus, Trash2, AlertCircle } from 'lucide-react'
import Ajv from 'ajv'
import addFormats from 'ajv-formats'
import Section from './components/ui/Section.jsx'
import Input from './components/ui/Input.jsx'
import TextArea from './components/ui/TextArea.jsx'
import Toggle from './components/ui/Toggle.jsx'
import Badge from './components/ui/Badge.jsx'
import ArrayOfStringsEditor from './components/editors/ArrayOfStringsEditor.jsx'
import KeyValueEditor from './components/editors/KeyValueEditor.jsx'
import TokenPatternsEditor from './components/editors/TokenPatternsEditor.jsx'
import SlotPatternsEditor from './components/editors/SlotPatternsEditor.jsx'
import ExtractionPatternsEditor from './components/editors/ExtractionPatternsEditor.jsx'
import ExamplesEditor from './components/editors/ExamplesEditor.jsx'
import ParameterSpecEditor from './components/editors/ParameterSpecEditor.jsx'
import ParameterListEditor from './components/editors/ParameterListEditor.jsx'
import KeyValueOfStringArray from './components/editors/KeyValueOfStringArray.jsx'
import ObjectArrayEditor from './components/editors/ObjectArrayEditor.jsx'

// Default schema - minimal structure for validation when no schema is loaded
const defaultSchema = {
  title: "Irene Voice Assistant - Intent Handler Donation Schema",
  version: "1.0",
  type: "object",
  properties: {
    schema_version: { type: "string" },
    handler_domain: { type: "string" },
    description: { type: "string" },
    method_donations: {
      type: "array",
      items: {
        type: "object",
        properties: {
          method_name: { type: "string" },
          intent_suffix: { type: "string" },
          phrases: {
            type: "array",
            items: { type: "string" },
            minItems: 1
          }
        },
        required: ["method_name", "intent_suffix", "phrases"]
      }
    }
  },
  required: ["schema_version", "handler_domain", "method_donations"]
}

function download(filename, text) {
  const el = document.createElement('a')
  el.setAttribute('href', 'data:text/json;charset=utf-8,' + encodeURIComponent(text))
  el.setAttribute('download', filename)
  el.style.display = 'none'
  document.body.appendChild(el)
  el.click()
  document.body.removeChild(el)
}

function fileToText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = reject
    reader.readAsText(file)
  })
}

function MethodDonationEditor({ value, onChange, globalParamNames }){
  const v = value ?? { method_name: '', intent_suffix: '', phrases: [''] }
  const set = (k, val) => onChange({ ...(v ?? {}), [k]: val })
  const methodParamNames = (v.parameters ?? []).map(p => p?.name).filter(Boolean)
  const knownParams = Array.from(new Set([...(globalParamNames ?? []), ...methodParamNames]))
  return (
    <div className="border rounded-2xl p-4 bg-white">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input label="Method name" value={v.method_name} onChange={(val)=>set('method_name', val)} />
        <Input label="Intent suffix" value={v.intent_suffix} onChange={(val)=>set('intent_suffix', val)} />
        <TextArea label="Description (optional)" value={v.description ?? ''} onChange={(val)=>set('description', val)} />
        <Input label="Boost (0–10)" type="number" value={v.boost ?? 1} onChange={(val)=>set('boost', val)} />
      </div>
      <ArrayOfStringsEditor label="Trigger phrases" value={v.phrases} onChange={(val)=>set('phrases', val)} addLabel="Add phrase" />
      <ArrayOfStringsEditor label="Key lemmas (optional)" value={v.lemmas ?? []} onChange={(val)=>set('lemmas', val)} addLabel="Add lemma" />
      <Section title="Parameters" subtitle="Parameters extracted for this method" defaultOpen={false}>
        <ParameterListEditor value={v.parameters ?? []} onChange={(val)=>set('parameters', val)} />
      </Section>
      <Section title="spaCy token patterns" subtitle="Each pattern is a sequence of tokens with attributes" defaultOpen={false}>
        <TokenPatternsEditor label="Patterns" value={v.token_patterns ?? []} onChange={(val)=>set('token_patterns', val)} />
      </Section>
      <Section title="spaCy slot patterns" subtitle="Per-slot patterns used to capture parameters" defaultOpen={false}>
        <SlotPatternsEditor label="Slots" value={v.slot_patterns ?? {}} onChange={(val)=>set('slot_patterns', val)} />
      </Section>
      <Section title="Training examples" defaultOpen={false}>
        <ExamplesEditor value={v.examples ?? []} onChange={(val)=>set('examples', val)} knownParams={knownParams} />
      </Section>
    </div>
  )
}

export default function App(){
  const [schema, setSchema] = useState(defaultSchema)
  const [data, setData] = useState(() => ({ schema_version: defaultSchema?.version ?? '1.0', handler_domain: '', description: '', method_donations: [] }))
  const [errors, setErrors] = useState([])
  const [valid, setValid] = useState(null)

  const ajv = useMemo(()=>{ const a = new Ajv({ allErrors: true, strict: false }); addFormats(a); return a; },[])
  const validator = useMemo(()=>{ try { return ajv.compile(schema); } catch (e) { console.error(e); return null; } }, [ajv, schema])

  useEffect(()=>{
    if(validator){
      const ok = validator(data)
      setValid(!!ok)
      setErrors(validator.errors ?? [])
    }
  }, [validator, data])

  const importJSON = async (file) => {
    try{
      const txt = await fileToText(file)
      const obj = JSON.parse(txt)
      setData(obj)
    }catch(e){ alert('Invalid JSON: ' + e?.message) }
  }
  const importSchema = async (file) => {
    try{
      const txt = await fileToText(file)
      const obj = JSON.parse(txt)
      setSchema(obj)
    }catch(e){ alert('Invalid JSON Schema: ' + e?.message) }
  }

  const addDonation = ()=> setData({ ...data, method_donations: [ ...(data.method_donations ?? []), { method_name: '', intent_suffix: '', phrases: [''] } ] })
  const setDonation = (idx, d)=> setData({ ...data, method_donations: (data.method_donations ?? []).map((o,i)=> i===idx ? d : o) })
  const delDonation = (idx)=> setData({ ...data, method_donations: (data.method_donations ?? []).filter((_,i)=> i!==idx) })

  const globalParamNames = (data.global_parameters ?? []).map(p=>p?.name).filter(Boolean)

  const exportJSON = ()=> download(`${data.handler_domain || 'donation'}.json`, JSON.stringify(data, null, 2))

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Irene Donation Editor</h1>
            <div className="text-sm text-gray-600">
              Schema: <Badge>{schema?.title || 'unknown'}</Badge> <Badge>v{schema?.version || '?'}</Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {valid ? <Badge tone="green"><CheckCircle2 className="w-4 h-4 mr-1"/> Valid</Badge> : valid===false ? <Badge tone="red"><XCircle className="w-4 h-4 mr-1"/> Invalid</Badge> : <Badge>Not validated</Badge>}
            <button onClick={exportJSON} className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl bg-white hover:bg-gray-50"><Download className="w-4 h-4"/> Export JSON</button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-4">
            <Section title="General" subtitle="Top-level information about this handler">
              <div className="grid grid-cols-1 gap-3">
                <Input label="Schema version" value={data.schema_version ?? ''} onChange={(v)=>setData({ ...data, schema_version: v })} required />
                <Input label="Handler domain" value={data.handler_domain ?? ''} onChange={(v)=>setData({ ...data, handler_domain: v })} required />
                <TextArea label="Description" value={data.description ?? ''} onChange={(v)=>setData({ ...data, description: v })} />
              </div>
            </Section>

            <Section title="Recognition patterns" subtitle="Used for can_handle and NLU">
              <ArrayOfStringsEditor label="Intent name patterns" value={data.intent_name_patterns ?? []} onChange={(v)=>setData({ ...data, intent_name_patterns: v })} addLabel="Add pattern" />
              <ArrayOfStringsEditor label="Action patterns" value={data.action_patterns ?? []} onChange={(v)=>setData({ ...data, action_patterns: v })} addLabel="Add pattern" />
              <ArrayOfStringsEditor label="Domain patterns" value={data.domain_patterns ?? []} onChange={(v)=>setData({ ...data, domain_patterns: v })} addLabel="Add pattern" />
              <ArrayOfStringsEditor label="Additional recognition patterns" value={data.additional_recognition_patterns ?? []} onChange={(v)=>setData({ ...data, additional_recognition_patterns: v })} addLabel="Add pattern" />
            </Section>

            <Section title="Language detection" subtitle="Language → [patterns]" defaultOpen={false}>
              <KeyValueOfStringArray label="Patterns by language" value={data.language_detection ?? {}} onChange={(v)=>setData({ ...data, language_detection: v })} />
            </Section>

            <Section title="Train keywords" subtitle="Optional" defaultOpen={false}>
              <ArrayOfStringsEditor label="Keywords" value={data.train_keywords ?? []} onChange={(v)=>setData({ ...data, train_keywords: v })} addLabel="Add keyword" />
            </Section>

            <Section title="Global parameters" subtitle="Shared across methods" defaultOpen={false}>
              <ParameterListEditor value={data.global_parameters ?? []} onChange={(v)=>setData({ ...data, global_parameters: v })} />
            </Section>

            <Section title="Fallback conditions" subtitle="Advanced" defaultOpen={false}>
              <ObjectArrayEditor label="Conditions" value={data.fallback_conditions ?? []} onChange={(v)=>setData({ ...data, fallback_conditions: v })} />
            </Section>

            <Section title="Negative patterns" subtitle="Advanced – patterns that should NOT match" defaultOpen={false}>
              <TokenPatternsEditor label="Negative patterns" value={data.negative_patterns ?? []} onChange={(v)=>setData({ ...data, negative_patterns: v })} />
            </Section>

            <Section title="Schema settings" subtitle="Load a donation schema or use the default" defaultOpen={false}>
              <div className="mb-3 p-3 bg-blue-50 rounded-xl text-sm text-blue-700">
                <div className="font-medium mb-1">💡 Schema Loading</div>
                <div>Load a JSON schema file to unlock full validation and editing features. You can import the schema from your Irene project's <code className="bg-blue-100 px-1 rounded">schemas/donation/v1.0.json</code> file.</div>
              </div>
              <div className="flex items-center gap-2">
                <label className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl bg-white hover:bg-gray-50 cursor-pointer">
                  <Upload className="w-4 h-4"/> Import schema JSON
                  <input type="file" accept="application/json" className="hidden" onChange={(e)=>{ const f=e.target.files?.[0]; if(f) importSchema(f); }} />
                </label>
                <button className="px-3 py-2 border rounded-xl hover:bg-gray-50" onClick={()=>setSchema(defaultSchema)}>Reset to default</button>
              </div>
              <div className="text-xs text-gray-500 mt-2">Current: {schema?.title} (v{schema?.version})</div>
            </Section>
          </div>

          <div className="lg:col-span-2 space-y-4">
            <Section title="Method donations" subtitle="Define one entry per handler method">
              <div className="flex flex-col gap-4">
                {(data.method_donations ?? []).map((d, idx)=>(
                  <div key={idx} className="relative">
                    <div className="absolute -top-3 left-3"> <Badge>#{idx+1}</Badge> </div>
                    <MethodDonationEditor value={d} onChange={(v)=>setDonation(idx, v)} globalParamNames={globalParamNames} />
                    <div className="flex justify-end mt-2">
                      <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>delDonation(idx)}><Trash2 className="w-4 h-4"/></button>
                    </div>
                  </div>
                ))}
                <button className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50" onClick={addDonation}><Plus className="w-4 h-4"/> Add method donation</button>
              </div>
            </Section>

            <Section title="Validation" subtitle="Against the active JSON Schema">
              {valid ? (
                <div className="flex items-center gap-2 text-green-700"><CheckCircle2 /> Looks good!</div>
              ) : valid===false ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-red-700"><AlertCircle/> Found {errors.length} issue(s)</div>
                  <ul className="list-disc pl-5 text-sm text-red-700">
                    {errors.map((e, i)=> <li key={i}><code className="bg-red-50 px-1 rounded">{e.instancePath || '/'}</code> – {e.message}</li>)}
                  </ul>
                </div>
              ) : (
                <div className="text-gray-600 text-sm">No results yet</div>
              )}
            </Section>

            <Section title="Raw JSON (optional)" subtitle="Peek under the hood" defaultOpen={false}>
              <div className="mb-2 text-sm text-gray-500">This is just for preview. You can keep using the form above.</div>
              <textarea className="w-full h-64 border rounded-xl p-3 font-mono text-sm" readOnly value={JSON.stringify(data, null, 2)} />
            </Section>

            <div className="flex items-center gap-2">
              <label className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl bg-white hover:bg-gray-50 cursor-pointer">
                <Upload className="w-4 h-4"/> Import donation JSON
                <input type="file" accept="application/json" className="hidden" onChange={(e)=>{ const f=e.target.files?.[0]; if(f) importJSON(f); }} />
              </label>
              <button onClick={exportJSON} className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl bg-white hover:bg-gray-50"><Download className="w-4 h-4"/> Export JSON</button>
            </div>
          </div>
        </div>

        <footer className="text-xs text-gray-500 text-center pt-4">Built for the Irene Voice Assistant donation schema v{schema?.version || '?'}. Load your own schema or use the default. All data stays in your browser.</footer>
      </div>
    </div>
  )
}
