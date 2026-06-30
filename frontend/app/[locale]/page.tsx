import { ChatWindow } from "@/components/chat/ChatWindow";

export default function Home() {
  return (
    <main className="flex-1 flex flex-col h-full p-4 max-w-5xl mx-auto w-full overflow-hidden">
      <div className="flex-1 overflow-hidden">
        <ChatWindow />
      </div>
    </main>
  );
}
