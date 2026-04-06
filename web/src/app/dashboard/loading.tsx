export default function Loading() {
  return (
    <div className="min-h-screen">
      <nav className="border-b border-white/5 bg-bg-primary/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center">
          <span className="text-xl font-black bg-gradient-to-r from-player to-banker bg-clip-text text-transparent">LAPLACE</span>
        </div>
      </nav>
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="h-8 w-48 bg-bg-card rounded-lg animate-pulse mb-8" />
        <div className="h-24 bg-bg-card rounded-2xl animate-pulse mb-8" />
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          {[1,2,3,4].map(i => <div key={i} className="h-20 bg-bg-card rounded-xl animate-pulse" />)}
        </div>
      </div>
    </div>
  )
}
