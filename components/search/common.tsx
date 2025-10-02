import { useInstantSearch, useRefinementList } from "react-instantsearch"
import { TypesenseInstantsearchAdapterOptions } from "typesense-instantsearch-adapter"

const devConfig = {
  key: "Wk0K3oMIE1ERRmwX0uLgEk3gGEGKNuQe",
  // key: "mfylP3FhQBBAmUiDTWZ9PNbhzTtVID1W",
  url: "https://o89yhjf824.execute-api.us-east-1.amazonaws.com/search"
}

export function getServerConfig(): TypesenseInstantsearchAdapterOptions["server"] {
  const key = process.env.NEXT_PUBLIC_TYPESENSE_SEARCH_API_KEY ?? devConfig.key
  const url = new URL(
    process.env.NEXT_PUBLIC_TYPESENSE_API_URL ?? devConfig.url
  )

  const protocol = url.protocol.startsWith("https") ? "https" : "http"
  const port = url.port ? Number(url.port) : protocol === "https" ? 443 : 80

  return {
    apiKey: key,
    nodes: [
      {
        host: url.hostname,
        protocol,
        port,
        path: url.pathname
      }
    ]
  }
}

function RefinementList({ attribute }: { attribute: string }) {
  useRefinementList({ attribute, limit: 500 })
  return null
}

type VirtualFilterType = "bill" | "testimony" | "hearing"

const getRefinementAttributesByFilterType = (type: VirtualFilterType) => {
  switch (type) {
    case "testimony":
      return ["authorDisplayName", "court", "position", "billId", "authorRole"]
    case "bill":
      return [
        "court",
        "currentCommittee",
        "city",
        "primarySponsor",
        "cosponsors",
        "topics.lvl1",
        "topics.lvl0"
      ]
    case "hearing":
      return ["month", "year", "chairNames", "committeeName", "locationCity"]
  }
}

export const VirtualFilters = ({ type }: { type: VirtualFilterType }) => (
  <>
    {getRefinementAttributesByFilterType(type).map(attribute => (
      <RefinementList key={attribute} attribute={attribute} />
    ))}
  </>
)

export type SearchStatus = "loading" | "empty" | "results"

export const useSearchStatus = (): SearchStatus => {
  const { results } = useInstantSearch()
  if (!results.query) return "loading"
  if (results.nbHits === 0) return "empty"
  return "results"
}
