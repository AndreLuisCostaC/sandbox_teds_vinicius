export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <section className="w-full max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">ERP Portal</h1>
        <p className="mt-2 text-sm text-slate-600">
          Authentication and RBAC are enabled via middleware. You will be redirected to the
          correct area based on your role.
        </p>
        <a
          href="/login"
          className="mt-6 inline-flex rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
        >
          Go to login
        </a>
      </section>
    </main>
  );
}
