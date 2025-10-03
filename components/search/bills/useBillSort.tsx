import { useMemo, useRef } from "react"
import { SortOptionInput } from "../common"

export const useBillSortOptions = (): SortOptionInput[] => {
  const now = useRef(new Date().getTime())

  return useMemo(
    () => [
      {
        labelKey: "sort_by.most_recent_testimony",
        value: "bills/sort/latestTestimonyAt:desc"
      },
      {
        labelKey: "sort_by.relevance",
        value: "bills/sort/_text_match:desc,testimonyCount:desc"
      },
      {
        labelKey: "sort_by.testimony_count",
        value: "bills/sort/testimonyCount:desc"
      },
      {
        labelKey: "sort_by.cosponsor_count",
        value: "bills/sort/cosponsorCount:desc"
      },
      {
        labelKey: "sort_by.next_hearing_date",
        value: "bills/sort/nextHearingAt:asc",
        configure: {
          numericRefinements: {
            nextHearingAt: {
              ">=": [now.current]
            } as any
          }
        }
      }
    ],
    []
  )
}
