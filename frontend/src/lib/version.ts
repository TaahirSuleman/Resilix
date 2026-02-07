const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? 'dev'
const BUILD_SHA = import.meta.env.VITE_BUILD_SHA ?? 'local'
const BUILD_TIME = import.meta.env.VITE_BUILD_TIME ?? 'unknown'

export function getBuildLabel(): string {
  const shortSha = BUILD_SHA.length > 7 ? BUILD_SHA.slice(0, 7) : BUILD_SHA
  return `${APP_VERSION} (${shortSha})`
}

export function getBuildTime(): string {
  return BUILD_TIME
}
