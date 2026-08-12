"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/AuthForm";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { token, isLoading, login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");

  useEffect(() => {
    if (!isLoading && token) router.replace("/diagnostic");
  }, [isLoading, token, router]);

  async function handleSubmit(email: string, password: string) {
    if (mode === "login") await login(email, password);
    else await register(email, password);
    router.replace("/diagnostic");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm items-center px-6">
      <AuthForm mode={mode} onModeChange={setMode} onSubmit={handleSubmit} />
    </main>
  );
}
