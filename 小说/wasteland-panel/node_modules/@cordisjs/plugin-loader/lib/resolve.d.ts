export type Resolve = (specifier: string) => string;
export declare function createResolve(baseUrl: string | undefined): Promise<Resolve | undefined>;
