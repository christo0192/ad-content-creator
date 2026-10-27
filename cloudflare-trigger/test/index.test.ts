// vitest (node env) for the ik-intelligence-trigger Worker — added 2026-10-27.
// fetch is always stubbed: nothing here can reach the Fly API.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, {
  CRON,
  JOBS_DAY,
  WEEKLY_DAY,
  authHeader,
  startMachine,
  startUrl,
  targetForDay,
  type Env,
} from "../src/index";

const ENV: Env = {
  FLY_TOKEN_JOBS: "FlyV1 fm2_jobs-secret",
  FLY_TOKEN_WEEKLY: "pat-weekly-secret",
  JOBS_APP: "ik-market-research-jobs",
  JOBS_MACHINE_ID: "7845393fe26338",
  WEEKLY_APP: "ik-market-research-weekly",
  WEEKLY_MACHINE_ID: "7812565f9d3378",
};
const JOBS_URL = "https://api.machines.dev/v1/apps/ik-market-research-jobs/machines/7845393fe26338/start";
const WEEKLY_URL = "https://api.machines.dev/v1/apps/ik-market-research-weekly/machines/7812565f9d3378/start";

type Event = Parameters<typeof worker.scheduled>[0];
type Ctx = Parameters<typeof worker.scheduled>[2];
const ctx = {} as Ctx;
const at = (isoTime: string): Event => ({ scheduledTime: Date.parse(isoTime), cron: CRON, noRetry() {} }) as Event;

let logs: string[];
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  logs = [];
  for (const level of ["log", "warn", "error"] as const) {
    vi.spyOn(console, level).mockImplementation((...args: unknown[]) => {
      logs.push(args.map(String).join(" "));
    });
  }
  fetchMock = vi.fn(async () => new Response('{"ok":true}', { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("targetForDay", () => {
  it("maps day 1 to the jobs machine and day 2 to the pipeline machine", () => {
    expect(JOBS_DAY).toBe(1);
    expect(WEEKLY_DAY).toBe(2);
    expect(targetForDay(1, ENV)).toEqual({
      label: "jobs",
      app: "ik-market-research-jobs",
      machineId: "7845393fe26338",
      token: "FlyV1 fm2_jobs-secret",
    });
    expect(targetForDay(2, ENV)).toEqual({
      label: "weekly",
      app: "ik-market-research-weekly",
      machineId: "7812565f9d3378",
      token: "pat-weekly-secret",
    });
  });

  it("returns null for every other day", () => {
    for (const day of [0, 3, 15, 28, 31]) expect(targetForDay(day, ENV)).toBeNull();
  });
});

describe("authHeader", () => {
  it("passes Fly deploy (macaroon) tokens through unchanged", () => {
    expect(authHeader("FlyV1 fm2_x")).toBe("FlyV1 fm2_x");
  });
  it("sends anything else as Bearer", () => {
    expect(authHeader("abc")).toBe("Bearer abc");
  });
  it("trims the trailing newline a piped `wrangler secret put` can leave", () => {
    expect(authHeader("FlyV1 fm2_x\r\n")).toBe("FlyV1 fm2_x");
    expect(authHeader("  abc\n")).toBe("Bearer abc");
  });
});

describe("startUrl / startMachine", () => {
  it("builds the exact Machines API start URL (encoded)", () => {
    expect(startUrl(targetForDay(1, ENV)!)).toBe(JOBS_URL);
    expect(startUrl({ label: "jobs", app: "a/b", machineId: "m 1", token: "t" })).toBe(
      "https://api.machines.dev/v1/apps/a%2Fb/machines/m%201/start",
    );
  });

  it("POSTs once with the auth header and truncates the body to 500 chars", async () => {
    const f = vi.fn(async () => new Response("x".repeat(2000), { status: 409 }));
    const r = await startMachine(targetForDay(2, ENV)!, f as unknown as typeof fetch);
    expect(r).toEqual({ ok: false, status: 409, body: "x".repeat(500) });
    expect(f).toHaveBeenCalledTimes(1);
    expect(f).toHaveBeenCalledWith(WEEKLY_URL, {
      method: "POST",
      headers: { Authorization: "Bearer pat-weekly-secret", "Content-Type": "application/json" },
    });
  });
});

describe("scheduled()", () => {
  it("day 1 starts the jobs machine exactly once with its FlyV1 token", async () => {
    await worker.scheduled(at("2026-11-01T03:30:00Z"), ENV, ctx);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(JOBS_URL);
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe("FlyV1 fm2_jobs-secret");
    expect(logs.join("\n")).toContain("jobs start OK (200) ik-market-research-jobs/7845393fe26338");
  });

  it("day 2 starts the pipeline machine exactly once with a Bearer token", async () => {
    await worker.scheduled(at("2026-11-02T03:30:00Z"), ENV, ctx);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(WEEKLY_URL);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer pat-weekly-secret");
  });

  it("dispatches on the UTC day, not the IST day", async () => {
    // 2026-10-31T23:00Z is already Nov 1 in IST — still UTC day 31: no start.
    await worker.scheduled(at("2026-10-31T23:00:00Z"), ENV, ctx);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("any other day logs and never calls fetch", async () => {
    await worker.scheduled(at("2026-11-15T03:30:00Z"), ENV, ctx);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(logs.join("\n")).toContain("UTC day 15: no target");
  });

  it("a missing / blank token or machine id never calls fetch", async () => {
    for (const env of [
      { ...ENV, FLY_TOKEN_JOBS: "" },
      { ...ENV, FLY_TOKEN_JOBS: "  \n" },
      { ...ENV, FLY_TOKEN_JOBS: undefined as unknown as string },
      { ...ENV, JOBS_MACHINE_ID: "" },
      { ...ENV, JOBS_APP: "" },
    ]) {
      await worker.scheduled(at("2026-11-01T03:30:00Z"), env, ctx);
    }
    expect(fetchMock).not.toHaveBeenCalled();
    expect(logs.filter((l) => l.includes("jobs: missing app/machine/token config"))).toHaveLength(5);
  });

  it("does not throw on a 500 from Fly", async () => {
    fetchMock.mockImplementation(async () => new Response("machine is in a non-startable state", { status: 500 }));
    await expect(worker.scheduled(at("2026-11-02T03:30:00Z"), ENV, ctx)).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(logs.join("\n")).toContain("weekly start FAILED (500)");
  });

  it("does not throw on a network error", async () => {
    fetchMock.mockImplementation(async () => {
      throw new TypeError("network down");
    });
    await expect(worker.scheduled(at("2026-11-01T03:30:00Z"), ENV, ctx)).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(logs.join("\n")).toContain("jobs fetch error:");
  });

  it("does not throw on a garbage scheduledTime", async () => {
    await expect(worker.scheduled({ scheduledTime: NaN, cron: CRON } as Event, ENV, ctx)).resolves.toBeUndefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("never logs a token", async () => {
    fetchMock.mockImplementation(async () => new Response("unauthorized", { status: 401 }));
    await worker.scheduled(at("2026-11-01T03:30:00Z"), ENV, ctx);
    await worker.scheduled(at("2026-11-02T03:30:00Z"), ENV, ctx);
    await worker.scheduled(at("2026-11-03T03:30:00Z"), ENV, ctx);
    const all = logs.join("\n");
    expect(all).not.toContain("fm2_jobs-secret");
    expect(all).not.toContain("pat-weekly-secret");
  });
});

describe("fetch()", () => {
  it("returns 405 (scheduled-only)", async () => {
    const res = await worker.fetch(new Request("https://example.com/"), ENV);
    expect(res.status).toBe(405);
  });
});

describe("wrangler.toml drift guard", () => {
  const toml = readFileSync(fileURLToPath(new URL("../wrangler.toml", import.meta.url)), "utf8");

  it("has exactly one cron and it equals CRON", () => {
    const m = toml.match(/^crons\s*=\s*\[([^\]]*)\]/m);
    expect(m).not.toBeNull();
    const crons = [...m![1].matchAll(/"([^"]*)"/g)].map((x) => x[1]);
    expect(crons).toEqual([CRON]);
  });

  it("targets the real machines", () => {
    const v = (key: string) => toml.match(new RegExp(`^${key}\\s*=\\s*"([^"]*)"`, "m"))?.[1];
    expect(v("JOBS_APP")).toBe(ENV.JOBS_APP);
    expect(v("JOBS_MACHINE_ID")).toBe(ENV.JOBS_MACHINE_ID);
    expect(v("WEEKLY_APP")).toBe(ENV.WEEKLY_APP);
    expect(v("WEEKLY_MACHINE_ID")).toBe(ENV.WEEKLY_MACHINE_ID);
    expect(v("name")).toBe("ik-intelligence-trigger");
  });
});
