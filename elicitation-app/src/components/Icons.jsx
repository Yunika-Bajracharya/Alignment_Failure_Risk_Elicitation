/**
 * Centralized icon mappings for all domain items.
 * Uses lucide-react — clean, minimal SVGs, no emojis.
 */
import {
  ShieldOff,
  ThumbsUp,
  Scale,
  EyeOff,
  Zap,
  Brain,
  Scroll,
  Crosshair,
  MessagesSquare,
  Layers,
  SlidersHorizontal,
  TrendingUp,
  Microscope,
  ListFilter,
  Shield,
  CheckCircle2,
  ChevronRight,
  Download,
  FileJson,
  FileSpreadsheet,
  ArrowLeft,
  ArrowRight,
  User,
  BookOpen,
  AlertTriangle,
  MapPin,
  Clock,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Target,
  Lock,
  Cpu,
  FlaskConical,
  Scan,
  Network,
  Gauge,
} from 'lucide-react';

/** Lucide icon component for each failure mode id */
export const FM_ICONS = {
  jailbreaking: ShieldOff,
  jailbreaking_generic: ShieldOff,
  sycophancy: ThumbsUp,
  sycophancy_generic: ThumbsUp,
  data_bias: Scale,
  data_bias_generic: Scale,
  deceptive_alignment: EyeOff,
  deceptive_alignment_generic: EyeOff,
  sleeper_agents: Zap,
  sleeper_agents_generic: Zap,
};

/** Lucide icon component for each alignment technique id */
export const TECH_ICONS = {
  rlhf: Brain,
  constitutional_ai: Scroll,
  adversarial_finetuning: Crosshair,
  ai_debate: MessagesSquare,
  ida: Layers,
  representation_engineering: SlidersHorizontal,
  w2sg: TrendingUp,
  mechanistic_interpretability: Microscope,
  constitutional_classifiers: ListFilter,
};

/** Fallback icon when id is not in map */
export const FallbackFMIcon = Shield;
export const FallbackTechIcon = Cpu;

/** Get an FM icon component by failure mode id */
export function getFMIcon(id) {
  return FM_ICONS[id] || FallbackFMIcon;
}

/** Get a technique icon component by technique id */
export function getTechIcon(id) {
  return TECH_ICONS[id] || FallbackTechIcon;
}

/* Re-export common UI icons for convenience */
export {
  CheckCircle2 as IconCheck,
  ChevronRight as IconChevronRight,
  ChevronDown as IconChevronDown,
  ChevronUp as IconChevronUp,
  Download as IconDownload,
  FileJson as IconJSON,
  FileSpreadsheet as IconCSV,
  ArrowLeft as IconArrowLeft,
  ArrowRight as IconArrowRight,
  User as IconUser,
  BookOpen as IconBook,
  AlertTriangle as IconWarning,
  MapPin as IconPin,
  Clock as IconClock,
  BarChart3 as IconChart,
  Target as IconTarget,
  Lock as IconLock,
  Shield as IconShield,
  FlaskConical as IconFlask,
  Scan as IconScan,
  Network as IconNetwork,
  Gauge as IconGauge,
};
