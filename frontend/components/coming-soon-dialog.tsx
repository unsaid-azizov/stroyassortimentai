'use client'

import * as React from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

interface ComingSoonDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
}

export function ComingSoonDialog({ open, onOpenChange, title }: ComingSoonDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>В разработке</DialogTitle>
          <DialogDescription>
            Раздел "{title}" находится в разработке и будет доступен в ближайшее время.
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end">
          <Button onClick={() => onOpenChange(false)}>Закрыть</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}



