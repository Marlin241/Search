import { RequireAuth } from "@/components/layout/RequireAuth";
import { Logo } from "@/components/common/Logo";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <div className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-gradient-to-br from-[#2d1b4e] via-[#4a2d7a] to-[#5b3a99] px-4 py-10">
        <div className="pointer-events-none absolute inset-0 opacity-30">
          <div className="absolute -top-[15%] -left-[10%] h-[50%] w-[50%] rounded-full bg-primary-400 blur-3xl" />
          <div className="absolute -bottom-[15%] -right-[10%] h-[50%] w-[50%] rounded-full bg-accent blur-3xl" />
        </div>

        <Logo className="relative z-10 mb-8 text-white" />

        <div className="relative z-10 flex w-full flex-col items-center">
          {children}
        </div>
      </div>
    </RequireAuth>
  );
}
