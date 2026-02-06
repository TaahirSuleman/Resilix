import React from 'react'
import { TimelineEvent } from '../types/ui'
import { AlertCircle, CheckCircle2, Info, Zap } from 'lucide-react'
import { motion } from 'framer-motion'

interface TimelineProps {
  events: TimelineEvent[]
}

export function Timeline({ events }: TimelineProps) {
  return (
    <div className="relative pl-2">
      <div className="absolute left-[19px] top-2 bottom-2 w-[2px] bg-gray-100" />

      <div className="space-y-6">
        {events.map((event, index) => (
          <motion.div
            key={event.id}
            initial={{
              opacity: 0,
              x: -10,
            }}
            animate={{
              opacity: 1,
              x: 0,
            }}
            transition={{
              delay: index * 0.1,
              duration: 0.3,
            }}
            className="relative flex gap-4 items-start group"
          >
            <div
              className={`
              relative z-10 flex items-center justify-center w-10 h-10 rounded-full border-4 border-white shadow-sm shrink-0
              ${getEventColor(event.type)}
            `}
            >
              {getEventIcon(event.type)}
            </div>

            <div className="pt-2">
              <div className="text-xs font-mono text-gray-400 mb-0.5">{event.timestamp}</div>
              <div className="text-sm text-gray-700 font-medium leading-relaxed">{event.description}</div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function getEventColor(type: TimelineEvent['type']) {
  switch (type) {
    case 'alert':
      return 'bg-red-50 text-red-600'
    case 'action':
      return 'bg-blue-50 text-blue-600'
    case 'success':
      return 'bg-green-50 text-green-600'
    case 'info':
      return 'bg-gray-50 text-gray-500'
    default:
      return 'bg-gray-50 text-gray-500'
  }
}

function getEventIcon(type: TimelineEvent['type']) {
  const className = 'w-4 h-4'
  switch (type) {
    case 'alert':
      return <AlertCircle className={className} />
    case 'action':
      return <Zap className={className} />
    case 'success':
      return <CheckCircle2 className={className} />
    case 'info':
      return <Info className={className} />
  }
}
