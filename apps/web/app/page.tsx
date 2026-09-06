import { redirect } from "next/navigation";

export default function RootPage() {
  // The dashboard layout resolves the session and sends signed-out visitors to
  // /login, so there is a single place that decides where a visitor belongs.
  redirect("/dashboard");
}
