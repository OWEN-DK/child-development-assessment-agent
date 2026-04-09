# System Configuration Page Design

## 1. Purpose
The current application has a `SystemConfigPage` that is not wired into the application's router, meaning users cannot access it to modify global system configurations. In the existing "RAG Evaluation" page, only a subset of hot-reloadable configurations are exposed via a sidebar panel (`ConfigTuningPanel`), which does not allow users to modify all parameters. The goal is to provide a dedicated, globally accessible System Configuration page and remove the partial configuration panel from the RAG Evaluation page to keep the UI clean.

## 2. Architecture & Changes
- **Router (`frontend/src/router/index.tsx`)**: Register the existing `SystemConfigPage` under a new route path `/system-config`.
- **Main Navigation (`frontend/src/App.tsx`)**: Add a new menu item "系统配置" (System Config) to the main top navigation layout, pointing to `/system-config`.
- **RAG Evaluation Page (`frontend/src/features/rag-evaluation/pages/RagEvaluationPage.tsx`)**: 
  - Remove the `ConfigTuningPanel` component import and usage.
  - Adjust the layout so the "leftPanel" (which contains the metrics and tabs) spans the full width, or remove the `rightPanel` entirely to ensure a clean, focused evaluation page.
- **Component Cleanup (`frontend/src/features/rag-evaluation/components/ConfigTuningPanel.tsx`)**:
  - The `ConfigTuningPanel` component can be safely deleted or marked as deprecated since it is no longer used.

## 3. Data Flow
- `SystemConfigPage` uses the existing `useConfigStore` to fetch, display, edit, and save all configuration fields.
- Saving changes in `SystemConfigPage` will invoke the backend API (`/api/v1/config`) and create a new configuration version.
- Other components (like RAG evaluation) will continue to fetch the active configuration when they load.

## 4. Testing
- Verify that clicking "系统配置" in the top navigation opens the full configuration form.
- Verify that modifying and saving a configuration correctly updates the global settings.
- Verify that the RAG Evaluation page renders correctly without the right-side configuration panel.
