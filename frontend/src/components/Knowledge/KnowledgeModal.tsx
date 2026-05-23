import { useState, useRef, type DragEvent } from 'react';
import { X, Upload, FileText, AlertTriangle, Check, Loader2, FolderOpen } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

interface KnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SUPPORTED_EXTENSIONS = [
  '.txt', '.md', '.markdown', '.json', '.csv', '.tsv',
  '.xml', '.yaml', '.yml', '.html', '.htm', '.log',
  '.py', '.js', '.ts', '.jsx', '.tsx',
  '.docx', '.pdf', '.xlsx',
];

const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'markdown', 'json', 'csv', 'tsv',
  'xml', 'yaml', 'yml', 'html', 'htm', 'log',
  'py', 'js', 'ts', 'jsx', 'tsx',
]);

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
  files: File[];
  content: string;
  fileCount: number;
  skippedCount: number;
}

export function KnowledgeModal({ isOpen, onClose }: KnowledgeModalProps) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const { uploadNewKnowledge } = useApp();

  if (!isOpen) return null;

  const resetForm = () => {
    setName(''); setContent(''); setFileInfo(null); setError(''); setIsDragOver(false);
  };

  const handleClose = () => { resetForm(); onClose(); };

  const processFiles = async (files: FileList | File[]) => {
    const fileArr = Array.from(files);
    const textFiles = fileArr.filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase() || '';
      return TEXT_EXTENSIONS.has(ext);
    });
    const skipped = fileArr.length - textFiles.length;

    if (textFiles.length === 0) {
      setError('所选文件中没有可读取的文本格式');
      return;
    }

    // Auto-fill name from first file/folder
    if (!name.trim()) {
      const first = fileArr[0];
      const base = first.name.replace(/\.[^.]+$/, '');
      setName(fileArr.length > 1 && first.webkitRelativePath
        ? first.webkitRelativePath.split('/')[0]
        : base);
    }

    // Read all text files
    const contents: string[] = [];
    for (const f of textFiles) {
      const text = await readFileAsText(f);
      if (text !== null) {
        const label = fileArr.length > 1 ? `\n## ${f.name}\n` : '';
        contents.push(label + text);
      }
    }
    const combined = contents.join('\n').slice(0, 50000);

    setFileInfo({ files: fileArr, content: combined, fileCount: textFiles.length, skippedCount: skipped });
    setContent(combined);
    setError('');
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files?.length) processFiles(files);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault(); setIsDragOver(false);
    if (e.dataTransfer.files.length) processFiles(e.dataTransfer.files);
  };

  const handleSubmit = async () => {
    if (!name.trim() || !content.trim()) return;
    setIsUploading(true); setError('');
    try {
      await uploadNewKnowledge(name.trim(), content.trim());
      resetForm(); onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    } finally { setIsUploading(false); }
  };

  const canSubmit = name.trim() && content.trim();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Upload size={16} className="text-indigo-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">导入知识库</h2>
          </div>
          <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">知识库名称</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="例如：天猫618活动规则"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent" />
          </div>

          {/* Upload zone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              上传文件或文件夹
            </label>
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
                isDragOver ? 'border-indigo-400 bg-indigo-50'
                  : fileInfo ? 'border-green-300 bg-green-50'
                  : 'border-gray-300'
              }`}
            >
              <input ref={fileInputRef} type="file" onChange={handleFileChange}
                accept={SUPPORTED_EXTENSIONS.join(',')} className="hidden" multiple />
              <input ref={folderInputRef} type="file" onChange={handleFileChange}
                /* @ts-expect-error webkitdirectory is non-standard */
                webkitdirectory="" directory="" className="hidden" />

              {fileInfo ? (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
                    <Check size={18} className="text-green-500" />
                  </div>
                  <div className="text-left flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-700">
                      已选择 {fileInfo.fileCount} 个文本文件
                      {fileInfo.skippedCount > 0 && <span className="text-amber-500">（{fileInfo.skippedCount} 个跳过）</span>}
                    </p>
                    <p className="text-xs text-gray-400">{fileInfo.content.length} 字符</p>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); resetForm(); }}
                    className="p-1.5 rounded-lg hover:bg-red-100 text-gray-400 hover:text-red-500">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div>
                  <Upload size={28} className="mx-auto mb-2 text-gray-300" />
                  <p className="text-sm text-gray-500 mb-3">
                    拖拽文件/文件夹，或点击下方按钮
                  </p>
                  <div className="flex items-center justify-center gap-3">
                    <button onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                      className="px-4 py-2 text-xs font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
                      <FileText size={14} className="inline mr-1" />
                      选择文件
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); folderInputRef.current?.click(); }}
                      className="px-4 py-2 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors">
                      <FolderOpen size={14} className="inline mr-1" />
                      选择文件夹
                    </button>
                  </div>
                  <p className="text-xs text-gray-400 mt-3">支持 txt, md, json, csv, xml, py 等文本格式</p>
                </div>
              )}
            </div>
          </div>

          {/* Text area */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {fileInfo ? '文本内容预览/编辑' : '直接粘贴文本'}
            </label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)}
              placeholder="粘贴规则文本或相关知识..."
              rows={fileInfo ? 4 : 8}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none font-mono" />
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl">
              <AlertTriangle size={14} className="text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-xl">
            <FileText size={14} className="text-blue-500 mt-0.5 shrink-0" />
            <p className="text-xs text-blue-700">
              文件夹会上传其中所有文本文件并合并为一个知识库。上传后由后端RAG系统分块、向量化并建立索引。
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 shrink-0">
          <button onClick={handleClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">取消</button>
          <button onClick={handleSubmit} disabled={!canSubmit || isUploading}
            className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm flex items-center gap-1.5">
            {isUploading ? <><Loader2 size={14} className="animate-spin" />导入中...</> : '导入知识库'}
          </button>
        </div>
      </div>
    </div>
  );
}
