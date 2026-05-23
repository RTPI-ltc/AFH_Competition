import { useState, useRef, type DragEvent } from 'react';
import { X, Upload, FileText, AlertTriangle, Check, Loader2 } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

interface KnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SUPPORTED_EXTENSIONS = [
  '.txt', '.md', '.markdown',
  '.json', '.csv', '.tsv',
  '.xml', '.yaml', '.yml',
  '.html', '.htm', '.log',
  '.py', '.js', '.ts', '.jsx', '.tsx',
  '.docx', '.pdf', '.xlsx',
];

const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'markdown', 'json', 'csv', 'tsv',
  'xml', 'yaml', 'yml', 'html', 'htm', 'log',
  'py', 'js', 'ts', 'jsx', 'tsx',
]);

/** Read file as text; returns null for binary formats */
function readFileAsText(file: File): Promise<string | null> {
  const ext = file.name.split('.').pop()?.toLowerCase() || '';
  if (TEXT_EXTENSIONS.has(ext)) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => resolve(null);
      reader.readAsText(file);
    });
  }
  return Promise.resolve(null);
}

interface FileInfo {
  file: File;
  content: string | null;
  parseError?: string;
}

export function KnowledgeModal({ isOpen, onClose }: KnowledgeModalProps) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { uploadNewKnowledge } = useApp();

  // --- ALL hooks above this line; conditional return below ---
  if (!isOpen) return null;

  const resetForm = () => {
    setName('');
    setContent('');
    setFileInfo(null);
    setError('');
    setIsDragOver(false);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const onFileSelected = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    if (!SUPPORTED_EXTENSIONS.includes('.' + ext)) {
      setError(`不支持的文件格式: .${ext}`);
      return;
    }
    if (!name.trim()) {
      setName(file.name.replace(/\.[^.]+$/, ''));
    }
    const text = await readFileAsText(file);
    const parseError = text === null
      ? `${ext.toUpperCase()} ⚠ 二进制格式，需安装解析库（如 mammoth、pdf.js、xlsx）方可提取文本`
      : undefined;
    setFileInfo({ file, content: text, parseError });
    if (text !== null) {
      setContent(text.slice(0, 50000));
      setError('');
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelected(file);
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;
    const useContent = content.trim();
    if (!useContent && !fileInfo?.parseError) return;
    setIsUploading(true);
    setError('');
    try {
      await uploadNewKnowledge(name.trim(), useContent);
      resetForm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    } finally {
      setIsUploading(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const canSubmit = name.trim() && (content.trim() || !!fileInfo?.parseError);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Upload size={16} className="text-indigo-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">导入知识库</h2>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">知识库名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：天猫618活动规则"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>

          {/* File drop zone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              上传文件 <span className="text-gray-400 font-normal">（txt, md, json, csv, xml 等文本格式）</span>
            </label>
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={() => setIsDragOver(false)}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                isDragOver ? 'border-indigo-400 bg-indigo-50'
                  : fileInfo ? 'border-green-300 bg-green-50'
                  : 'border-gray-300 hover:border-indigo-300 hover:bg-gray-50'
              }`}
            >
              <input ref={fileInputRef} type="file" onChange={handleFileChange}
                accept={SUPPORTED_EXTENSIONS.join(',')} className="hidden" />

              {fileInfo ? (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
                    {fileInfo.parseError
                      ? <AlertTriangle size={18} className="text-amber-500" />
                      : <Check size={18} className="text-green-500" />}
                  </div>
                  <div className="text-left flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-700 truncate">{fileInfo.file.name}</p>
                    <p className="text-xs text-gray-400">
                      {formatSize(fileInfo.file.size)}
                      {fileInfo.parseError
                        ? ` · 无法直接解析`
                        : ` · ${fileInfo.content?.length || 0} 字符`}
                    </p>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); setFileInfo(null); setContent(''); }}
                    className="p-1.5 rounded-lg hover:bg-red-100 text-gray-400 hover:text-red-500">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div>
                  <Upload size={28} className="mx-auto mb-2 text-gray-300" />
                  <p className="text-sm text-gray-500">拖拽文件到此处，或<span className="text-indigo-600">点击上传</span></p>
                  <p className="text-xs text-gray-400 mt-1">支持 txt, md, json, csv, xml 等格式</p>
                </div>
              )}
            </div>

            {fileInfo?.parseError && (
              <div className="flex items-start gap-2 mt-2 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                <AlertTriangle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                <p className="text-xs text-amber-700">{fileInfo.parseError}</p>
              </div>
            )}
          </div>

          {/* Text area */}
          {(!fileInfo || fileInfo.parseError || fileInfo.content !== null) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                {fileInfo ? '文本内容预览/编辑' : '直接粘贴文本'}
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="粘贴规则文本或相关知识..."
                rows={fileInfo ? 4 : 8}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none font-mono"
              />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl">
              <AlertTriangle size={14} className="text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-xl">
            <FileText size={14} className="text-blue-500 mt-0.5 shrink-0" />
            <p className="text-xs text-blue-700">
              上传的文本将由后端RAG系统自动分块、向量化并建立索引，在对话中Agent可引用知识库内容辅助规则解析。
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 shrink-0">
          <button onClick={handleClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">取消</button>
          <button onClick={handleSubmit} disabled={!canSubmit || isUploading}
            className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm flex items-center gap-1.5">
            {isUploading ? <><Loader2 size={14} className="animate-spin" />导入中...</> : '导入知识库'}
          </button>
        </div>
      </div>
    </div>
  );
}
