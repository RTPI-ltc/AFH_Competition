import { useState } from 'react';
import { Folder, FolderOpen, Plus, Check, X, Pencil, FileBarChart } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

interface ProjectListProps {
  onSummarizeProject: (projectId: string) => void;
}

export function ProjectList({ onSummarizeProject }: ProjectListProps) {
  const { state, switchProject, createNewProject, loadProjects, renameProject } = useApp();
  const [isNew, setIsNew] = useState(false);
  const [newName, setNewName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  const handleCreate = async () => {
    const name = newName.trim() || '新项目';
    await createNewProject(name);
    setIsNew(false);
    setNewName('');
    loadProjects();
  };

  const startRename = (id: string, name: string) => {
    setEditingId(id);
    setEditName(name);
  };

  const confirmRename = async () => {
    if (editingId && editName.trim()) {
      await renameProject(editingId, editName.trim());
    }
    setEditingId(null);
    setEditName('');
  };

  return (
    <div className="px-2">
      <div className="flex items-center justify-between px-3 py-1">
        <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">项目</span>
        <button
          onClick={() => setIsNew(!isNew)}
          className="p-0.5 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition-colors"
          title="新建项目"
        >
          <Plus size={14} />
        </button>
      </div>

      {isNew && (
        <div className="px-3 py-1 mb-1">
          <div className="flex items-center gap-1">
            <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); }}
              placeholder="项目名称..." autoFocus
              className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500" />
            <button onClick={handleCreate} className="p-1 rounded hover:bg-indigo-100 text-gray-400 hover:text-indigo-600">
              <Check size={14} />
            </button>
          </div>
        </div>
      )}

      <div className="space-y-0.5">
        {state.projects.map((proj) => {
          const isActive = proj.id === state.currentProjectId;
          const isEditing = editingId === proj.id;

          if (isEditing) {
            return (
              <div key={proj.id} className="flex items-center gap-1 px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') confirmRename(); if (e.key === 'Escape') setEditingId(null); }}
                  autoFocus
                  className="flex-1 px-1 py-0 text-xs border border-indigo-300 rounded bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                <button onClick={confirmRename} className="p-0.5 rounded hover:bg-green-100 text-gray-400 hover:text-green-600">
                  <Check size={12} />
                </button>
                <button onClick={() => setEditingId(null)} className="p-0.5 rounded hover:bg-red-100 text-gray-400 hover:text-red-500">
                  <X size={12} />
                </button>
              </div>
            );
          }

          return (
            <div key={proj.id} className="group flex items-center gap-2">
              <button
                onClick={() => switchProject(proj.id)}
                className={`flex items-center gap-2 flex-1 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  isActive ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {isActive ? <FolderOpen size={14} className="text-indigo-500" /> : <Folder size={14} />}
                <span
                  className="truncate flex-1 text-left"
                  onDoubleClick={(e) => { e.stopPropagation(); startRename(proj.id, proj.name); }}
                  title="双击重命名"
                >
                  {proj.name}
                </span>
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onSummarizeProject(proj.id); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-emerald-100 text-gray-400 hover:text-emerald-600 transition-all"
                title="项目汇总"
              >
                <FileBarChart size={11} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); startRename(proj.id, proj.name); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition-all"
                title="重命名"
              >
                <Pencil size={11} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
