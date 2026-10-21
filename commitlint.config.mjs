export default {
  extends: ['@commitlint/config-conventional'],
  // Dependabot writes release notes into the body with long URLs; its subject is still conventional.
  ignores: [(message) => message.includes('Signed-off-by: dependabot[bot]')],
};
