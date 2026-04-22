/* eslint-disable react/prop-types */
import { useUpdateWorkspace } from "@features/workspaces/api";
import CancelIcon from "@mui/icons-material/Cancel";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import SaveAltIcon from "@mui/icons-material/SaveAlt";
import {
  Card,
  CardHeader,
  CardContent,
  Box,
  Typography,
  Grid,
  TextField,
  Tooltip,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
} from "@mui/material";
import { useWorkspaces } from "context/workspaces";
import { useState, useCallback, useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { toast } from "react-toastify";

const GIT_PLATFORM_OPTIONS = [
  { value: "github", label: "GitHub (github.com)" },
  { value: "gitlab", label: "GitLab (gitlab.com)" },
  { value: "gitea", label: "Gitea" },
  { value: "bitbucket", label: "Bitbucket (bitbucket.org)" },
];

const WorkspaceSecretsCard = () => {
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const { register, getValues, resetField, control, setValue } = useForm();
  const { handleUpdateWorkspace, workspace } = useWorkspaces();

  const { mutateAsync: patchWorkspace } = useUpdateWorkspace({
    workspaceId: workspace?.id,
  });

  const tokenFilled =
    workspace?.git_access_token_filled ?? workspace?.github_access_token_filled ?? false;

  useEffect(() => {
    if (workspace) {
      handleUpdateWorkspace(workspace);
      setValue("git_platform_type", workspace.git_platform_type ?? "github");
      setValue("git_platform_url", workspace.git_platform_url ?? "");
      setValue("git_username", workspace.git_username ?? "");
    }
  }, [workspace, handleUpdateWorkspace, setValue]);

  const handleSave = useCallback(
    async (e: React.SyntheticEvent<HTMLButtonElement>) => {
      e.preventDefault();
      setIsEditing(false);

      if (!workspace) {
        toast.error("Workspace not selected.");
        return;
      }

      if (e.currentTarget.ariaLabel === "clear") {
        patchWorkspace({
          git_access_token: null,
          github_access_token: null,
        })
          .then((response) => {
            toast.success("Git token cleared.");
            handleUpdateWorkspace(response);
            resetField(`git-token-workspace-${workspace.id}`, { keepTouched: false });
          })
          .catch(() => toast.error("Error while clearing token"));
        return;
      }

      const token = getValues(`git-token-workspace-${workspace.id}`);
      const platformType = getValues("git_platform_type");
      const platformUrl = getValues("git_platform_url");
      const username = getValues("git_username");

      // Allow saving platform settings even without a new token
      const payload: Record<string, string | null> = {
        git_platform_type: platformType || null,
        git_platform_url: platformUrl || null,
        git_username: username || null,
      };

      if (token && token !== "******") {
        payload.git_access_token = token;
        payload.github_access_token = token; // backward compat
      }

      patchWorkspace(payload)
        .then((response) => {
          toast.success("Git platform settings updated.");
          handleUpdateWorkspace(response);
        })
        .catch(() => toast.error("Error while updating settings"));
    },
    [workspace, getValues, patchWorkspace, resetField, handleUpdateWorkspace],
  );

  if (!workspace) {
    return <h1>Workspace not selected.</h1>;
  }

  return (
    <Card variant="outlined">
      <CardHeader
        title="Git Platform Settings"
        titleTypographyProps={{ variant: "h6" }}
      />
      <CardContent>
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Connect your workspace to a Git platform (GitHub, GitLab, Gitea, Bitbucket, or
            a self-hosted instance). Providing an access token unlocks private repositories
            and raises API rate limits. All credentials are encrypted at rest.
          </Typography>
        </Box>

        <form>
          <Grid container spacing={2}>
            {/* Platform Type */}
            <Grid item xs={12} sm={6}>
              <Controller
                name="git_platform_type"
                control={control}
                defaultValue={workspace.git_platform_type ?? "github"}
                render={({ field }) => (
                  <FormControl fullWidth disabled={!isEditing}>
                    <InputLabel id="git-platform-type-label">Platform Type</InputLabel>
                    <Select
                      labelId="git-platform-type-label"
                      label="Platform Type"
                      {...field}
                    >
                      {GIT_PLATFORM_OPTIONS.map((opt) => (
                        <MenuItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
              />
            </Grid>

            {/* Platform URL (for self-hosted) */}
            <Grid item xs={12} sm={6}>
              <TextField
                InputLabelProps={{ shrink: true }}
                label="Platform URL (leave blank for default)"
                placeholder="https://gitlab.mycompany.com"
                disabled={!isEditing}
                fullWidth
                {...register("git_platform_url")}
                defaultValue={workspace.git_platform_url ?? ""}
              />
            </Grid>

            {/* Username */}
            <Grid item xs={12} sm={6}>
              <TextField
                InputLabelProps={{ shrink: true }}
                label="Username (optional, for HTTP Basic auth)"
                disabled={!isEditing}
                fullWidth
                {...register("git_username")}
                defaultValue={workspace.git_username ?? ""}
              />
            </Grid>

            {/* Access Token */}
            <Grid item xs={12} sm={5}>
              <TextField
                InputLabelProps={{ shrink: true }}
                label="Access Token / Password"
                disabled={!isEditing}
                defaultValue={tokenFilled ? "******" : ""}
                type="password"
                fullWidth
                {...register(`git-token-workspace-${workspace.id}`)}
              />
            </Grid>

            {/* Action Buttons */}
            <Grid item xs={12} sm={1} sx={{ display: "flex", alignItems: "center" }}>
              {isEditing ? (
                <Box>
                  <Tooltip title="Save">
                    <IconButton aria-label="save" onClick={handleSave}>
                      <SaveAltIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Clear token">
                    <IconButton aria-label="clear" onClick={handleSave}>
                      <DeleteIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Cancel">
                    <IconButton
                      aria-label="cancel"
                      onClick={() => setIsEditing(false)}
                    >
                      <CancelIcon />
                    </IconButton>
                  </Tooltip>
                </Box>
              ) : (
                <Tooltip title="Edit">
                  <IconButton
                    aria-label="edit"
                    onClick={() => setIsEditing(true)}
                  >
                    <EditIcon />
                  </IconButton>
                </Tooltip>
              )}
            </Grid>
          </Grid>
        </form>

        <Divider sx={{ my: 2 }} />
        <Typography variant="caption" color="text.secondary">
          Supported platforms: GitHub · GitLab · Gitea · Bitbucket · any self-hosted
          instance reachable over HTTPS. For SSH key authentication, configure the key
          path in the server-side environment variable{" "}
          <code>DOMINO_WORKFLOWS_GIT_SSH_KEY_PATH</code>.
        </Typography>
      </CardContent>
    </Card>
  );
};

export default WorkspaceSecretsCard;
