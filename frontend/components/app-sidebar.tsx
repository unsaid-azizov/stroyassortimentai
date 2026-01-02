"use client"

import * as React from "react"
import {
  IconDashboard,
  IconFileAi,
  IconInnerShadowTop,
  IconUsers,
  IconBriefcase,
  IconCalculator,
  IconSettings,
} from "@tabler/icons-react"

import { NavDocuments } from "@/components/nav-documents"
import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import { NavUser } from "@/components/nav-user"
import { ComingSoonDialog } from "@/components/coming-soon-dialog"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const [comingSoonOpen, setComingSoonOpen] = React.useState(false)
  const [comingSoonTitle, setComingSoonTitle] = React.useState("")

  const handleComingSoon = (title: string) => {
    setComingSoonTitle(title)
    setComingSoonOpen(true)
  }

const data = {
  user: {
    name: "shadcn",
    email: "m@example.com",
    avatar: "/avatars/shadcn.jpg",
  },
  navMain: [
    {
        title: "Главная",
        url: "/dashboard",
      icon: IconDashboard,
    },
        {
        title: "Менеджер продаж",
        url: "/sales-manager",
        icon: IconFileAi,
    },
        {
          title: "Настройки",
          url: "/settings",
          icon: IconSettings,
        },
    {
        title: "HR",
      url: "#",
        icon: IconBriefcase,
        onClick: () => handleComingSoon("HR"),
    },
    {
        title: "Бухгалтер",
      url: "#",
        icon: IconCalculator,
        onClick: () => handleComingSoon("Бухгалтер"),
    },
    {
        title: "Лиды",
        url: "/leads",
      icon: IconUsers,
    },
  ],
    navClouds: [],
    navSecondary: [],
    documents: [],
}

  return (
    <>
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="data-[slot=sidebar-menu-button]:!p-1.5"
            >
                <a href="/dashboard">
                <IconInnerShadowTop className="!size-5" />
                  <span className="text-base font-semibold">СтройАссортимент</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
          {data.documents.length > 0 && <NavDocuments items={data.documents} />}
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
    </Sidebar>
      <ComingSoonDialog
        open={comingSoonOpen}
        onOpenChange={setComingSoonOpen}
        title={comingSoonTitle}
      />
    </>
  )
}


