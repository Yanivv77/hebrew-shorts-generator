import { useState } from 'react'
import AnalyzeStep from '../components/creator/AnalyzeStep'
import ActorStep from '../components/creator/ActorStep'
import GenerateStep from '../components/creator/GenerateStep'
import PostGenStep from '../components/creator/PostGenStep'

const STEPS = ['ניתוח', 'שחקן', 'יצירה', 'שיתוף']

export default function CreatorPage() {
  const [step, setStep] = useState(0)
  const [analyzeResult, setAnalyzeResult] = useState(null)
  const [selectedScript, setSelectedScript] = useState(null)
  const [actorImageUrl, setActorImageUrl] = useState(null)
  const [, setJobId] = useState(null)
  const [jobResult, setJobResult] = useState(null)

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold
              ${i < step ? 'bg-indigo-600 text-white' : i === step ? 'bg-indigo-500 text-white' : 'bg-zinc-800 text-zinc-500'}`}>
              {i + 1}
            </div>
            <span className={`text-sm ${i === step ? 'text-white' : 'text-zinc-500'}`}>{label}</span>
            {i < STEPS.length - 1 && <div className="w-6 h-px bg-zinc-700 mx-1" />}
          </div>
        ))}
      </div>

      {step === 0 && (
        <AnalyzeStep
          onComplete={(result, script) => {
            setAnalyzeResult(result)
            setSelectedScript(script)
            setStep(1)
          }}
        />
      )}
      {step === 1 && (
        <ActorStep
          script={selectedScript}
          onComplete={url => { setActorImageUrl(url); setStep(2) }}
        />
      )}
      {step === 2 && (
        <GenerateStep
          scripts={analyzeResult?.scripts || []}
          selectedScript={selectedScript}
          actorImageUrl={actorImageUrl}
          onComplete={(id, result) => { setJobId(id); setJobResult(result); setStep(3) }}
        />
      )}
      {step === 3 && (
        <PostGenStep
          jobResult={jobResult}
          selectedScript={selectedScript}
        />
      )}
    </div>
  )
}
