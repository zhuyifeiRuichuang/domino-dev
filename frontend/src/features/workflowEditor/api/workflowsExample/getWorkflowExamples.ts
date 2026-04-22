import { type QueryConfig } from "@services/clients/react-query.client";
import { useQuery, skipToken } from "@tanstack/react-query";
import axios, { type AxiosError } from "axios";
import { type WorkflowPieceData } from "features/workflowEditor/context/types";
import { toast } from "react-toastify";
import { type Edge, type Node } from "reactflow";

interface JSONFile {
  workflowPieces: Record<string, Piece>;
  workflowPiecesData: WorkflowPieceData;
  workflowNodes: Node[];
  workflowEdges: Edge[];
}

export type WorkflowsGalleryExamples = Array<{
  title: string;
  description: string;
  jsonFile: JSONFile;
  levelTag: "Advanced" | "Beginner" | "Intermediate";
}>;

export const useWorkflowsExamples = (
  fetch: boolean,
  config: QueryConfig<WorkflowsGalleryExamples> = {},
) => {
  return useQuery({
    queryKey: ["WORKFLOWS-EXAMPLES"],
    queryFn: fetch ? async () => await getWorkflowsExample() : skipToken,
    throwOnError(e, _query) {
      const message =
        ((e as AxiosError<{ detail?: string }>).response?.data?.detail ??
          e?.message) ||
        "Something went wrong";

      toast.error(message, {
        toastId: message,
      });

      return false;
    },
    ...config,
  });
};

const REPO_URL =
  "https://raw.githubusercontent.com/Tauffer-Consulting/domino_pieces_gallery/main/workflows_gallery";

const LOCAL_INDEX_URL = "/workflows_gallery/index.json";
const LOCAL_BASE_URL = "/workflows_gallery";

type GithubReposContent = Array<{
  title: string;
  description: string;
  jsonFile: string;
  levelTag: "Advanced" | "Beginner" | "Intermediate";
}>;

const getWorkflowsExample: () => Promise<WorkflowsGalleryExamples> =
  async () => {
    // 优先从本地静态文件读取（构建阶段已下载打包到镜像中）
    try {
      const { data: indexData } = await axios.get<GithubReposContent>(
        LOCAL_INDEX_URL,
        { timeout: 3000 },
      );
      const jsons: WorkflowsGalleryExamples = [];
      for (const value of indexData) {
        const { data: json } = await axios.get<JSONFile>(
          `${LOCAL_BASE_URL}/${value.jsonFile}`,
          { timeout: 3000 },
        );
        jsons.push({ ...value, jsonFile: json });
      }
      return jsons;
    } catch {
      // 本地文件不存在时（开发模式），尝试从远程 GitHub 仓库获取
      try {
        const { data } = await axios.get<GithubReposContent>(
          `${REPO_URL}/index.json`,
          { timeout: 5000 },
        );
        const jsons: WorkflowsGalleryExamples = [];
        for (const value of data) {
          const { data: json } = await axios.get<JSONFile>(
            `${REPO_URL}/${value.jsonFile}`,
            { timeout: 5000 },
          );
          jsons.push({ ...value, jsonFile: json });
        }
        return jsons;
      } catch {
        return [];
      }
    }
  };
