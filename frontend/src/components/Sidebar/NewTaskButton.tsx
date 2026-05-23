import { Plus } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

interface NewTaskButtonProps {
  onTaskStarted?: () => void;
}

export function NewTaskButton({ onTaskStarted }: NewTaskButtonProps) {
  const { startNewTask, state } = useApp();

  const handleClick = async () => {
    await startNewTask();
    onTaskStarted?.();
  };

  return (
    <button
      onClick={handleClick}
      disabled={state.isLoading}
      className="flex items-center gap-2 w-full px-3 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
    >
      <Plus size={16} />
      <span>开启新任务</span>
    </button>
  );
}
