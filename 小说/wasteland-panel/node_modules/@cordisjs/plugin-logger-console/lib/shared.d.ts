import { Context, Exporter, Formatter, Message } from 'cordis';
import z from 'schemastery';
export type ColorSupportLevel = 0 | 1 | 2 | 3;
export interface LabelStyle {
    width?: number;
    margin?: number;
    align?: 'left' | 'right';
}
export declare namespace ConsoleExporter {
    interface Config {
        colors?: false | ColorSupportLevel;
        maxLength?: number;
        levels?: Record<string, number>;
        showDiff?: boolean;
        showTime?: string;
        label?: LabelStyle;
    }
}
export declare class ConsoleExporter implements Exporter {
    ctx: Context;
    static readonly name = "logger-console";
    static readonly Config: z<ConsoleExporter.Config>;
    colors: false | ColorSupportLevel;
    maxLength?: number;
    levels?: Record<string, number>;
    showDiff: boolean;
    showTime: string;
    label?: LabelStyle;
    timestamp: number;
    formatters: Record<string, Formatter>;
    constructor(ctx: Context, config?: ConsoleExporter.Config);
    getDefaults(): {
        colors: false | ColorSupportLevel;
        showTime: string;
        showDiff: boolean;
    };
    export(message: Message): void;
    render(message: Message): string;
}
export default ConsoleExporter;
