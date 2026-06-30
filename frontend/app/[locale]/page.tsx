import { ChatWindow } from "@/components/chat/ChatWindow";

export default function Home() {
  return (
    <main className="flex-1 flex flex-col h-[calc(100vh-64px)] p-4 max-w-5xl mx-auto w-full">
      <div className="flex-1 overflow-hidden">
        <ChatWindow />
      </div>
    </main>
  );
}
