import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

const commonProps: IconProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}

export function CheckCircleIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M9 12l2 2 4-4" />
      <circle cx="12" cy="12" r="9" />
    </svg>
  )
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  )
}

export function SendIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  )
}

export function SparkleIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M12 3l1.8 4.4L18 9l-4.2 1.6L12 15l-1.8-4.4L6 9l4.2-1.6z" />
    </svg>
  )
}

export function DocumentIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M14 3v4a1 1 0 001 1h4" />
      <path d="M17 21H7a2 2 0 01-2-2V5a2 2 0 012-2h7l5 5v11a2 2 0 01-2 2z" />
    </svg>
  )
}

export function MenuIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </svg>
  )
}

export function CloseIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </svg>
  )
}

export function ExternalLinkIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M14 5h5v5" />
      <path d="M10 14L19 5" />
      <path d="M19 13v6H5V5h6" />
    </svg>
  )
}

export function AlertIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 4.2L2.7 18a2 2 0 001.8 3h15a2 2 0 001.8-3L13.7 4.2a2 2 0 00-3.4 0z" />
    </svg>
  )
}

export function RefreshIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M20 6v5h-5" />
      <path d="M4 18v-5h5" />
      <path d="M6.1 9a7 7 0 0111.7-2.6L20 11" />
      <path d="M17.9 15a7 7 0 01-11.7 2.6L4 13" />
    </svg>
  )
}

export function TrashIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M4 7h16" />
      <path d="M9 7V4h6v3" />
      <path d="M7 7l1 13h8l1-13" />
      <path d="M10 11v5" />
      <path d="M14 11v5" />
    </svg>
  )
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg {...commonProps} {...props}>
      <path d="M9 18l6-6-6-6" />
    </svg>
  )
}
