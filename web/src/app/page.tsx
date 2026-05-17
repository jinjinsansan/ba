import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase-server'
import OperatorWall from './_components/OperatorWall'
import LoginForm from './_components/LoginForm'

export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (user) redirect('/me')

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[1.45fr_1fr]">
      {/* Hide the marketing wall on small screens — too much for mobile login */}
      <div className="hidden lg:block">
        <OperatorWall />
      </div>
      <LoginForm />
    </div>
  )
}
