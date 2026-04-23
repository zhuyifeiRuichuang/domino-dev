type DeployMode = "local-compose" | "local-k8s-dev" | "local-k8s";

export interface IEnvironment {
  API_URL: string;
  DOMINO_DEPLOY_MODE: DeployMode;
}

/**
 * 获取运行时环境变量（由 entrypoint.sh 注入到 window.__DOMINO_ENV__）
 * 如果不存在则回退到构建时变量（import.meta.env）
 */
const getRuntimeEnv = (): Partial<IEnvironment> => {
  if (typeof window !== "undefined" && (window as any).__DOMINO_ENV__) {
    return (window as any).__DOMINO_ENV__;
  }
  return {};
};

export const environment: IEnvironment = {
  API_URL: getRuntimeEnv().API_URL ?? (import.meta.env.API_URL as string) ?? "http://localhost:8000",
  DOMINO_DEPLOY_MODE: (getRuntimeEnv().DOMINO_DEPLOY_MODE ?? import.meta.env.DOMINO_DEPLOY_MODE ?? "docker-compose") as DeployMode,
};
