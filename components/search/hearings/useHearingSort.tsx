import { useMemo } from "react"
import { useTranslation } from "next-i18next"
import { SortByWithConfigurationItem } from "../SortBy"

export const useHearingSort = () => {
  const { t } = useTranslation("search")

  return useMemo<SortByWithConfigurationItem[]>(
    () => [
      {
        label: t("sort_by.earliest_hearing"),
        value: "hearings/sort/startsAt:asc"
      },
      {
        label: t("sort_by.latest_hearing"),
        value: "hearings/sort/startsAt:desc"
      },
      {
        label: t("sort_by.relevance"),
        value: "hearings/sort/_text_match:desc,startsAt:asc"
      }
    ],
    [t]
  )
}
