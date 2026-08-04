/** A monetary amount; floating-point amounts are deliberately not supported. */
export interface Money {
  readonly minorUnits: bigint;
  readonly currency: string;
}

/** Tenant context required by every tenant-owned command and event. */
export interface TenantContext {
  readonly tenantId: string;
  readonly actorId: string;
}
