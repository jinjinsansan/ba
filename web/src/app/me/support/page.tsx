import { PageHeader } from '@/components/ui/PageHeader'
import SupportForm from '../../dashboard/SupportForm'

export default function SupportPage() {
  return (
    <div>
      <PageHeader
        kicker="Member · Support"
        title="サポート"
        sub="技術的な問題・アカウントに関する質問はこちらから"
      />
      <SupportForm />
    </div>
  )
}
