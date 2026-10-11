import {
  Rocket,
  Spline,
  Split,
  Merge,
  CheckCheck,
  Ban,
  // Import other icons as needed
  LetterText,
  Bot,
  Text,
  Image,
  Play,
} from 'lucide-react';

export const iconMapping: Record<
  string,
  React.FC<React.SVGProps<SVGSVGElement>>
> = {
  Rocket: Rocket,
  Spline: Spline,
  Split: Split,
  Merge: Merge,
  CheckCheck: CheckCheck,
  Ban: Ban,
  LetterText: LetterText,
  Bot: Bot,
  Text: Text,
  Image: Image,
  Play: Play,
  // Add other mappings here
};
