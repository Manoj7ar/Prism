"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = SummaryView;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
function SummaryView() {
    const [content, setContent] = (0, react_1.useState)('Loading summary...');
    (0, react_1.useEffect)(() => {
        if (window.electron && window.electron.onUpdateSummary) {
            window.electron.onUpdateSummary((newContent) => {
                setContent(newContent);
            });
        }
    }, []);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "min-h-screen bg-slate-900 text-slate-100 p-8 flex flex-col gap-6", children: [(0, jsx_runtime_1.jsx)("header", { className: "flex items-center justify-between border-b border-slate-800 pb-4", children: (0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "p-2 bg-blue-500/10 rounded-lg", children: (0, jsx_runtime_1.jsx)(lucide_react_1.FileText, { className: "w-6 h-6 text-blue-400" }) }), (0, jsx_runtime_1.jsx)("h1", { className: "text-xl font-bold", children: "Task Summary" })] }) }), (0, jsx_runtime_1.jsx)("main", { className: "flex-1 overflow-y-auto", children: (0, jsx_runtime_1.jsx)("div", { className: "prose prose-invert max-w-none", children: (0, jsx_runtime_1.jsx)("p", { className: "text-slate-300 leading-relaxed whitespace-pre-wrap", children: content }) }) }), (0, jsx_runtime_1.jsx)("footer", { className: "text-xs text-slate-500 text-center border-t border-slate-800 pt-4", children: "Press Esc to close this window" })] }));
}
