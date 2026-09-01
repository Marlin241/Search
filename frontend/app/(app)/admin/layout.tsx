"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user?.is_admin) router.replace("/dashboard");
  }, [isLoading, user, router]);

  if (isLoading || !user?.is_admin) return null;
  return <>{children}</>;
}
