import { Context, Service } from 'cordis';
declare module 'cordis' {
    interface Context extends Pick<TimerService, 'interval' | 'timeout' | 'throttle' | 'debounce' | 'setTimeout' | 'setInterval'> {
        timer: TimerService;
    }
}
type WithDispose<T> = T & {
    dispose: () => void;
};
export declare class TimerService extends Service {
    constructor(ctx: Context);
    /** @deprecated use `ctx.timeout()` instead */
    setTimeout(callback: () => void, delay: number): () => void;
    /** @deprecated use `ctx.interval()` instead */
    setInterval(callback: () => void, delay: number): () => void;
    timeout(callback: () => void, delay: number): () => void;
    timeout(delay: number): Promise<void>;
    interval(callback: () => void, delay: number): () => void;
    interval<R = any>(delay: number): AsyncIterableIterator<void, R, void>;
    private _schedule;
    throttle<F extends (...args: any[]) => void>(callback: F, delay: number, noTrailing?: boolean): WithDispose<F>;
    debounce<F extends (...args: any[]) => void>(callback: F, delay: number): WithDispose<F>;
}
export default TimerService;
