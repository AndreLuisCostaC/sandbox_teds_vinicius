"use client";

export default function EmployeePage() {
  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-10">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Employee Workspace</h1>
          <p className="text-sm text-slate-600">
            Limited area for non-admin users based on RBAC middleware checks.
          </p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
        >
          Logout
        </button>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-medium text-slate-900">RBAC Status</h2>
        <p className="mt-2 text-sm text-slate-600">
          Access granted. Employee users are redirected here after successful login.
        </p>
      </section>
    </main>
  );
}
