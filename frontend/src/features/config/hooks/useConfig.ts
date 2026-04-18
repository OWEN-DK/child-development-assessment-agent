import { useConfigStore, type ModePreference } from '../stores/configStore';
import { configApi } from '@/api/config';
import type { ConfigResetRequest } from '@/api/config/types';
import { DiagnosticService } from '../services/diagnosticService';

export function useConfig() {
  const store = useConfigStore();

  const loadConfig = async () => {
    store.setIsLoading(true);
    try {
      const response = await configApi.getConfig();
      const configFields = Array.isArray(response.config) ? response.config : [];

      const originalValues: Record<string, any> = {};
      configFields.forEach((field: any) => {
        originalValues[field.key] = field.current_value ?? field.default_value;
      });

      store.setConfigFields(configFields);
      store.setDraftChanges({});
      store.setOriginalValues(originalValues);
      store.setActiveVersion(response.active_version);
    } catch (error) {
      console.error('Failed to load config:', error);
      store.setConfigFields([]);
    } finally {
      store.setIsLoading(false);
    }
  };

  const loadVersions = async () => {
    try {
      const versions = await configApi.listVersions();
      store.setVersions(Array.isArray(versions) ? versions : []);
      if (!store.activeVersion && versions.length > 0) {
        store.setActiveVersion(versions[0].id);
      }
    } catch (error) {
      console.error('Failed to load versions:', error);
      store.setVersions([]);
    }
  };

  const updateDraft = (key: string, value: any) => {
    store.updateDraft(key, value);
    
    // 触发防抖健康诊断
    const currentConfig = { ...store.originalValues, ...store.draftChanges, [key]: value };
    DiagnosticService.scheduleDiagnostic(
      currentConfig,
      store.healthDiagnostic,
      (result) => {
        store.setHealthDiagnostic(result);
        store.setIsDiagnosing(false);
      },
      () => store.setIsDiagnosing(true)
    );
  };

  const saveConfig = async (description: string) => {
    if (Object.keys(store.draftChanges).length === 0) return;

    store.setIsSaving(true);
    try {
      const mergedConfig = { ...store.originalValues, ...store.draftChanges };

      await configApi.updateConfig({
        config_snapshot: mergedConfig,
        description,
        created_by: 'user',
      });

      store.setDraftChanges({});
      store.setOriginalValues(mergedConfig);

      await loadConfig();
      await loadVersions();
    } catch (error) {
      console.error('Failed to save config:', error);
      throw error;
    } finally {
      store.setIsSaving(false);
    }
  };

  const rollbackToVersion = async (versionId: string) => {
    try {
      await configApi.rollbackToVersion(versionId);
      await loadConfig();
      await loadVersions();
    } catch (error) {
      console.error('Failed to rollback:', error);
      throw error;
    }
  };

  const resetToFactory = async () => {
    try {
      const confirmed = window.confirm(
        '确认恢复出厂设置？\n\n此操作将清除所有自定义配置，是否继续？'
      );

      if (!confirmed) return;

      const resetRequest: ConfigResetRequest = {
        confirm: true,
        reason: '用户手动恢复'
      };

      await configApi.resetToFactory(resetRequest);
      await loadConfig();
      await loadVersions();
    } catch (error) {
      console.error('Failed to reset:', error);
      throw error;
    }
  };

  const switchMode = (mode: ModePreference) => {
    store.setModePreference(mode);
    localStorage.setItem('configModePreference', mode);
  };

  const runHealthDiagnostic = async () => {
    store.setIsDiagnosing(true);
    const currentConfig = { ...store.originalValues, ...store.draftChanges };
    const result = await DiagnosticService.runDiagnostic(currentConfig, store.healthDiagnostic);
    store.setHealthDiagnostic(result);
    store.setIsDiagnosing(false);
  };

  return {
    ...store,
    loadConfig,
    loadVersions,
    updateDraft,
    saveConfig,
    rollbackToVersion,
    resetToFactory,
    switchMode,
    runHealthDiagnostic,
  };
}