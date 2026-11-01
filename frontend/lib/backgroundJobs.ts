import {
  createBackgroundJobsClient,
  JOB_STATUSES,
  jobTypeLabel,
  parseJobJson,
  type BackgroundJob,
} from "@workforceos/contracts/client";
import { api } from "./api";

export type { BackgroundJob };
export { JOB_STATUSES, jobTypeLabel, parseJobJson };

const client = createBackgroundJobsClient(api);

export const {
  fetchAdminBackgroundJobs,
  retryBackgroundJob,
  cancelBackgroundJob,
  runBackgroundJobNow,
  updateBackgroundJobStatus,
  scheduleWorkflowScanJob,
  scheduleAttendanceScanJob,
} = client;
