import SupportForm from '../../dashboard/SupportForm'

export default function SupportPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="hud-label mb-2">Support</div>
        <h1 className="text-2xl sm:text-3xl font-hud">サポート</h1>
        <p className="text-text-muted text-sm mt-2">技術的な問題・アカウントに関する質問はこちらから。</p>
      </div>
      <SupportForm />
    </div>
  )
}
