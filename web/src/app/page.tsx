import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase-server'
import LoginForm from './_components/LoginForm'

export default async function HomePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (user) redirect('/me')
  return <LoginForm />
}
