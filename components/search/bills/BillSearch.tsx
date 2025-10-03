import { currentGeneralCourt, generalCourts } from "functions/src/shared"
import { useRef } from "react"
import { SearchPage } from "../common"
import { BillHit } from "./BillHit"

const extractLastSegmentOfRefinements = (items: any[]) => {
  return items.map(item => {
    if (item.label != "topics.lvl1") return item
    const newRefinements = item.refinements.map(
      (refinement: { label: string }) => {
        const lastPartOfLabel = refinement.label.includes(">")
          ? refinement.label.split(" > ").pop()
          : refinement.label
        return { ...refinement, label: lastPartOfLabel }
      }
    )
    return { ...item, label: "Tags", refinements: newRefinements }
  })
}

export const BillSearch = () => {
  const now = useRef(new Date().getTime())
  const sortOptions = [
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
  ]
  return (
    <SearchPage
      searchType="bill"
      hitComponent={BillHit}
      filterConfig={{
        hierarchicalMenu: { attributes: ["topics.lvl0", "topics.lvl1"] },
        filters: [
          {
            attribute: "court",
            transformItems: items =>
              items
                .map(i => ({
                  ...i,
                  label: generalCourts[parseInt(i.value, 10)]?.Name ?? i.label
                }))
                .sort((a, b) => Number(b.value) - Number(a.value))
          },
          { attribute: "currentCommittee" },
          { attribute: "city" },
          { attribute: "primarySponsor" },
          { attribute: "cosponsors" }
        ]
      }}
      sortOptions={sortOptions}
      searchParameters={{
        query_by: "number,title,body",
        exclude_fields: "body"
      }}
      virtualFacetAttributes={[
        "court",
        "currentCommittee",
        "city",
        "primarySponsor",
        "cosponsors",
        "topics.lvl1",
        "topics.lvl0"
      ]}
      currentRefinementsProps={{
        excludedAttributes: ["nextHearingAt"],
        transformItems: extractLastSegmentOfRefinements
      }}
      initialUiState={{
        [sortOptions[0].value]: {
          refinementList: { court: [String(currentGeneralCourt)] }
        }
      }}
    />
  )
}
